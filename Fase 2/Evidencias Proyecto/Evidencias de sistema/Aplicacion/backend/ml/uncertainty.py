"""Offline trajectory-level forecast bands and paired cluster bootstrap.

The model is frozen. Only calibration trajectories determine forecast radius.
Neither these synthetic intervals nor bootstrap ranges enable operational ML.
"""
import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from app.services.kinetics import FEATURES, VERSION
from .causal_dataset import STRIDE_HOURS, TARGET_VERSION
from .causal_pipeline import STATUS, load_dataset, matrix, sha, versions, write_json
from .robustness import POLICIES, load_stress, predict, reference

CONTRACT = "trajectory-uncertainty-v1"
SCORE = "max_absolute_forecast_error_per_calibration_trajectory"
DEFAULT_ALPHA = .1
DEFAULT_REPLICATES = 2000
DEFAULT_SEED = 20261118
CONFIDENCE = .95


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def conformal_radius(scores, alpha):
    """Finite-sample rank over trajectories; never clip an out-of-range rank."""
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be finite and strictly between zero and one")
    if any(not np.isfinite(value) or value < 0 for value in scores):
        raise ValueError("Scores must be finite nonnegative errors")
    rank = int((Decimal(len(scores) + 1) * (1 - Decimal(str(alpha)))).to_integral_value(rounding=ROUND_CEILING))
    radius = float(sorted(scores)[rank - 1]) if scores and rank <= len(scores) else None
    return {"alpha": alpha, "nominal_coverage": 1 - alpha, "trajectories": len(scores),
            "rank": rank, "radius_brix": radius,
            "interval_status": "finite_experimental" if radius is not None else "insufficient_calibration_trajectories"}


def calibrate_rows(bundle, rows, trajectories, alpha=DEFAULT_ALPHA):
    """Do not examine validation/test features or targets when choosing radius."""
    calibration = sorted((r for r in rows if r['split'] == 'calibration'),
                         key=lambda r: (r['process_id'], r['hour']))
    expected = {t['spec']['process_id'] for t in trajectories if t['split'] == 'calibration'}
    if {r['process_id'] for r in calibration} != expected or not expected:
        raise ValueError("Calibration trajectory inventory mismatch")
    forecast = [r for r in calibration if r['eligible'] and r['forecast_target'] is not None]
    if {r['process_id'] for r in forecast} != expected:
        raise ValueError("A calibration trajectory has no eligible forecast targets; do not silently drop it")
    values = bundle['forecaster'].predict(matrix(forecast))
    errors = defaultdict(list)
    for row, prediction in zip(forecast, values):
        errors[row['process_id']].append(abs(float(prediction) - row['forecast_target']))
    scores = [{'process_id': ident, 'windows': len(errors[ident]), 'score_brix': max(errors[ident])}
              for ident in sorted(expected)]
    # The calibration identity contains only columns used to obtain these scores.
    inputs = [{key: row[key] for key in ('process_id', 'seed', 'hour', 'eligible', 'forecast_target', *FEATURES)}
              for row in calibration]
    return {**conformal_radius([r['score_brix'] for r in scores], alpha),
            'score': SCORE, 'calibration_inputs_sha256': digest(inputs),
            'calibration_processes': sorted(expected), 'scores': scores,
            'forecast_hours': 24, 'coverage_unit': 'all emitted eligible 24h forecasts within one complete trajectory',
            'guarantee': 'nominal only in this stratified synthetic experiment; exchangeability not established'}


def load_reference(dataset_dir, model_dir):
    manifest, training = reference(dataset_dir, model_dir)
    rows, _ = load_dataset(dataset_dir)
    bundle = joblib.load(model_dir / 'experimental.joblib')  # Local trusted artifacts only.
    if (bundle['features'] != list(FEATURES) or bundle['feature_version'] != VERSION
            or bundle['target_version'] != TARGET_VERSION or bundle['status'] != STATUS
            or bundle['threshold'] != training['threshold']
            or bundle['dataset_sha256'] != manifest['dataset_sha256']):
        raise ValueError('Frozen model contract mismatch')
    # Cross-check manifest partitions against rows, rather than trusting labels alone.
    identities = {t['spec']['process_id']: (t['spec']['seed'], t['split']) for t in manifest['trajectories']}
    if len(identities) != len(manifest['trajectories']):
        raise ValueError('Duplicate manifest process')
    if {r['process_id'] for r in rows} != set(identities) or any(
            identities.get(r['process_id']) != (r['seed'], r['split']) for r in rows):
        raise ValueError('Manifest/row partition mismatch')
    for split in ('train', 'calibration', 'validation'):
        risk_ids = sorted({r['process_id'] for r in rows if r['split'] == split and r['eligible'] and r['risk_target'] is not None})
        if training['fit_processes'][split] != risk_ids:
            raise ValueError('Frozen model partition inventory mismatch')
    return rows, manifest, training, bundle


def calibrate(reference_dataset_dir, model_dir, output, alpha=DEFAULT_ALPHA):
    rows, manifest, training, bundle = load_reference(reference_dataset_dir, model_dir)
    result = {**calibrate_rows(bundle, rows, manifest['trajectories'], alpha),
        'contract': CONTRACT, 'status': STATUS, 'feature_version': VERSION, 'target_version': TARGET_VERSION,
        'reference_dataset_sha256': manifest['dataset_sha256'], 'artifact_sha256': training['artifact_sha256'],
        'uncertainty_code_sha256': sha(Path(__file__)), **versions()}
    if sha(model_dir / 'experimental.joblib') != training['artifact_sha256']:
        raise ValueError('Frozen model changed during calibration')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'intervals.json', result)
    return result


def load_intervals(directory, rows, manifest, training, bundle):
    stored = json.loads((directory / 'intervals.json').read_text(encoding='utf-8'))
    if (stored['contract'] != CONTRACT or stored['status'] != STATUS
            or stored['feature_version'] != VERSION or stored['target_version'] != TARGET_VERSION
            or stored['reference_dataset_sha256'] != manifest['dataset_sha256']
            or stored['artifact_sha256'] != training['artifact_sha256']
            or stored['uncertainty_code_sha256'] != sha(Path(__file__))):
        raise ValueError('Interval artifact contract/hash mismatch')
    expected = calibrate_rows(bundle, rows, manifest['trajectories'], stored['alpha'])
    if any(stored.get(key) != value for key, value in expected.items()):
        raise ValueError('Interval artifact differs from calibration-only reconstruction')
    return stored


# Additive sufficient statistics retain process multiplicity under resampling.
STAT_NAMES = ('windows', 'eligible', 'events', 'detected', 'risk_n', 'brier_sum', 'false_positives',
              'forecast_targets', 'forecast_n', 'absolute_error_sum', 'interval_n', 'covered', 'width_sum',
              'process_with_interval', 'process_all_emitted_covered', 'process_with_targets', 'process_all_targets_covered')


def process_statistics(bundle, rows, trajectories, radius):
    if radius is not None and (not np.isfinite(radius) or radius < 0):
        raise ValueError('Invalid interval radius')
    ids = {t['spec']['process_id']: t for t in trajectories}
    if set(r['process_id'] for r in rows) != set(ids):
        raise ValueError('Evaluation trajectory inventory mismatch')
    _, _, _, risk, forecast = predict(bundle, rows)
    stats = {ident: dict.fromkeys(STAT_NAMES, 0.) for ident in ids}
    for ident, t in ids.items():
        stats[ident]['events'] = int(t['event'] is not None)
    for row in rows:
        s = stats[row['process_id']]
        s['windows'] += 1
        s['eligible'] += int(row['eligible'])
        s['forecast_targets'] += int(row['forecast_target'] is not None)
    for row in risk:
        s = stats[row['process_id']]
        s['risk_n'] += 1
        s['brier_sum'] += (row['probability'] - row['target']) ** 2
        s['false_positives'] += int(row['alarm'] and row['target'] == 0)
        s['detected'] = max(s['detected'], int(row['alarm'] and row['target'] == 1))
    interval_rows = []
    for row in forecast:
        s = stats[row['process_id']]
        s['forecast_n'] += 1
        s['absolute_error_sum'] += abs(row['prediction'] - row['target'])
        lower = row['prediction'] - radius if radius is not None else None
        upper = row['prediction'] + radius if radius is not None else None
        covered = lower <= row['target'] <= upper if radius is not None else None
        if radius is not None:
            s['interval_n'] += 1
            s['covered'] += int(covered)
            s['width_sum'] += 2 * radius
        interval_rows.append({**row, 'lower_brix': lower, 'upper_brix': upper, 'covered': covered,
                              'interval_status': 'finite_experimental' if radius is not None else 'insufficient_calibration_trajectories'})
    result = []
    for ident in sorted(ids):
        s = stats[ident]
        s['process_with_interval'] = int(s['interval_n'] > 0)
        s['process_all_emitted_covered'] = int(s['interval_n'] > 0 and s['covered'] == s['interval_n'])
        s['process_with_targets'] = int(s['forecast_targets'] > 0)
        s['process_all_targets_covered'] = int(s['forecast_targets'] > 0 and s['covered'] == s['forecast_targets'])
        result.append({'process_id': ident, 'scenario': ids[ident]['spec']['scenario'], **s})
    return result, interval_rows


def summarize(totals):
    def ratio(a, b):
        return a / b if b else None
    return {'abstention_rate': ratio(totals['windows'] - totals['eligible'], totals['windows']),
            'event_recall_all': ratio(totals['detected'], totals['events']),
            'brier': ratio(totals['brier_sum'], totals['risk_n']),
            'false_positive_windows_per_eligible_day': ratio(totals['false_positives'], totals['risk_n'] * STRIDE_HOURS / 24),
            'forecast_mae_brix': ratio(totals['absolute_error_sum'], totals['forecast_n']),
            'interval_availability': ratio(totals['interval_n'], totals['forecast_targets']),
            'interval_window_coverage': ratio(totals['covered'], totals['interval_n']),
            'interval_mean_width_brix': ratio(totals['width_sum'], totals['interval_n']),
            'trajectory_emitted_coverage': ratio(totals['process_all_emitted_covered'], totals['process_with_interval']),
            'trajectory_all_targets_served_and_covered': ratio(totals['process_all_targets_covered'], totals['process_with_targets'])}


def cluster_draws(processes, replicates=DEFAULT_REPLICATES, seed=DEFAULT_SEED):
    if not isinstance(replicates, int) or not 100 <= replicates <= 20000:
        raise ValueError('Use 100..20000 bootstrap replicates')
    if not processes or len({p['process_id'] for p in processes}) != len(processes):
        raise ValueError('Bootstrap requires unique trajectories')
    strata = defaultdict(list)
    for index, process in enumerate(processes):
        strata[process['scenario']].append(index)
    rng = np.random.default_rng(seed)
    draws = np.concatenate([rng.choice(indices, size=(replicates, len(indices)), replace=True)
                            for _, indices in sorted(strata.items())], axis=1)
    return draws, {name: len(indices) for name, indices in sorted(strata.items())}


def bootstrap_summary(processes, draws, strata):
    data = np.array([[p[name] for name in STAT_NAMES] for p in processes], dtype=float)
    point = summarize(dict(zip(STAT_NAMES, data.sum(axis=0))))
    samples = [summarize(dict(zip(STAT_NAMES, values))) for values in data[draws].sum(axis=1)]
    intervals = {}
    for name, estimate in point.items():
        values = [s[name] for s in samples if s[name] is not None]
        supported = len(processes) >= 2 and all(size >= 2 for size in strata.values()) and len(values) == len(samples)
        bounds = np.quantile(values, [.025, .975]).tolist() if values and supported else [None, None]
        intervals[name] = {'estimate': estimate, 'lower': bounds[0], 'upper': bounds[1],
                           'defined_replicates': len(values), 'total_replicates': len(samples),
                           'degenerate': bool(supported and bounds[0] == bounds[1]),
                           'status': 'approximate_percentile' if supported else 'not_estimable'}
    return {'point': point, 'bootstrap_95': intervals,
            'counts': dict(zip(STAT_NAMES, data.sum(axis=0).tolist()))}, samples


def paired_difference(clean_samples, fault_samples):
    result = {}
    for name in clean_samples[0]:
        values = [b[name] - a[name] for a, b in zip(clean_samples, fault_samples)
                  if a[name] is not None and b[name] is not None]
        bounds = np.quantile(values, [.025, .975]).tolist() if len(values) == len(clean_samples) else [None, None]
        result[name] = {'lower': bounds[0], 'upper': bounds[1], 'defined_replicates': len(values)}
    return result


def evaluate(reference_dataset_dir, model_dir, interval_dir, output, stress_dataset_dir=None,
             replicates=DEFAULT_REPLICATES, seed=DEFAULT_SEED):
    rows, manifest, training, bundle = load_reference(reference_dataset_dir, model_dir)
    interval = load_intervals(interval_dir, rows, manifest, training, bundle)
    test_trajectories = [t for t in manifest['trajectories'] if t['split'] == 'test']
    datasets = {'original_test': {'clean': ([r for r in rows if r['split'] == 'test'], test_trajectories)}}
    stress_hash = None
    if stress_dataset_dir is not None:
        stress_rows, stress_manifest = load_stress(stress_dataset_dir, manifest, training)
        stress_hash = stress_manifest['dataset_sha256']
        datasets['stress_test'] = {policy: ([r for r in stress_rows if r['policy'] == policy],
                                          stress_manifest['trajectories']) for policy in POLICIES}
    report = {'contract': CONTRACT, 'status': STATUS, 'interval_artifact_sha256': sha(interval_dir / 'intervals.json'),
        'artifact_sha256': training['artifact_sha256'], 'reference_dataset_sha256': manifest['dataset_sha256'],
        'stress_dataset_sha256': stress_hash, 'interval_calibration': interval,
        'bootstrap': {'unit': 'trajectory', 'stratified_by': 'scenario', 'paired_across_fault_policies': True,
                      'replicates': replicates, 'seed': seed, 'nominal_confidence': CONFIDENCE,
                      'method': 'percentile; fixed model and calibration; not population or real-wine guarantees'},
        'datasets': {}, 'uncertainty_code_sha256': sha(Path(__file__)), **versions()}
    predictions = {}
    for dataset, policies in datasets.items():
        summaries, predictions[dataset], sampled = {}, {}, {}
        draws, strata, identity = None, None, None
        for policy, (subset, trajectories) in policies.items():
            processes, forecasts = process_statistics(bundle, subset, trajectories, interval['radius_brix'])
            keys = [(p['process_id'], p['scenario']) for p in processes]
            if draws is None:
                draws, strata = cluster_draws(processes, replicates, seed)
                identity = keys
            elif keys != identity:
                raise ValueError('Policies do not share identical paired trajectories')
            summary, samples = bootstrap_summary(processes, draws, strata)
            summary['by_process'] = processes
            summary['by_scenario'] = {}
            for scenario in strata:
                selected = [p for p in processes if p['scenario'] == scenario]
                sd, ss = cluster_draws(selected, replicates, seed)
                summary['by_scenario'][scenario] = bootstrap_summary(selected, sd, ss)[0]
            summaries[policy], sampled[policy] = summary, samples
            predictions[dataset][policy] = forecasts
        for policy in policies:
            summaries[policy]['paired_difference_vs_clean_95'] = paired_difference(sampled['clean'], sampled[policy])
            if any(n < 2 for n in strata.values()):
                for value in summaries[policy]['paired_difference_vs_clean_95'].values():
                    value['lower'] = value['upper'] = None
        report['datasets'][dataset] = {'strata': strata, 'policies': summaries,
                                      'bootstrap_draws_sha256': digest(draws.tolist())}
    if sha(model_dir / 'experimental.joblib') != training['artifact_sha256']:
        raise ValueError('Frozen model changed during evaluation')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'evaluation.json', report)
    write_json(output / 'forecast_intervals.json', predictions)
    return {dataset: {policy: value['point'] for policy, value in result['policies'].items()}
            for dataset, result in report['datasets'].items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('calibrate', 'evaluate'):
        sub = commands.add_parser(name)
        sub.add_argument('--reference-dataset-dir', required=True, type=Path)
        sub.add_argument('--model-dir', required=True, type=Path)
        sub.add_argument('--output-dir', required=True, type=Path)
        if name == 'calibrate':
            sub.add_argument('--alpha', type=float, default=DEFAULT_ALPHA)
        else:
            sub.add_argument('--interval-dir', required=True, type=Path)
            sub.add_argument('--stress-dataset-dir', type=Path)
            sub.add_argument('--replicates', type=int, default=DEFAULT_REPLICATES)
            sub.add_argument('--seed', type=int, default=DEFAULT_SEED)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    args['output'] = args.pop('output_dir')
    result = {'calibrate': calibrate, 'evaluate': evaluate}[command](**args)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
