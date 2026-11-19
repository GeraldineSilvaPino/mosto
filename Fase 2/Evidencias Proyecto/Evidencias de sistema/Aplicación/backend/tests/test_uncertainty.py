from copy import deepcopy
import json

import numpy as np
import pytest

from app.services.kinetics import FEATURES
from ml import uncertainty as u
from ml.causal_pipeline import sha
from test_robustness import experiment


class ConstantForecaster:
    def predict(self, values):
        return np.zeros(len(values))


def calibration_fixture(count=15):
    rows, trajectories = [], []
    for ident in range(1, count + 1):
        trajectories.append({'spec': {'process_id': ident}, 'split': 'calibration'})
        for hour, error in ((24, ident / 10), (27, ident / 2)):
            rows.append({**dict.fromkeys(FEATURES, 1.), 'split': 'calibration', 'process_id': ident,
                         'seed': ident, 'hour': hour, 'eligible': True, 'forecast_target': error})
    rows.append({**dict.fromkeys(FEATURES, 2.), 'split': 'test', 'process_id': 999,
                 'seed': 999, 'hour': 24, 'eligible': True, 'forecast_target': 999})
    return rows, trajectories


def test_finite_sample_rank_uses_trajectory_count_and_does_not_clip():
    assert u.conformal_radius(list(range(1, 16)), .1)['radius_brix'] == 15
    assert u.conformal_radius(list(range(1, 16)), .1)['rank'] == 15
    assert u.conformal_radius(list(range(1, 16)), .05)['radius_brix'] is None
    assert u.conformal_radius(list(range(1, 10)), .1)['radius_brix'] == 9
    assert u.conformal_radius(list(range(1, 9)), .1)['radius_brix'] is None
    assert u.conformal_radius([], .1)['interval_status'] == 'insufficient_calibration_trajectories'


@pytest.mark.parametrize('alpha', [0, 1, -.1, float('nan'), float('inf')])
def test_invalid_nominal_levels_rejected(alpha):
    with pytest.raises(ValueError):
        u.conformal_radius([1], alpha)


def test_calibration_ignores_other_splits_and_uses_max_error_per_process():
    rows, trajectories = calibration_fixture()
    bundle = {'forecaster': ConstantForecaster()}
    result = u.calibrate_rows(bundle, rows, trajectories)
    assert result['radius_brix'] == 7.5
    assert result['trajectories'] == 15 and len(result['scores']) == 15
    assert all(s['windows'] == 2 for s in result['scores'])
    poisoned = deepcopy(rows)
    poisoned[-1].update({name: float('nan') for name in FEATURES})
    poisoned[-1]['forecast_target'] = -99999
    poisoned.append({**poisoned[-1], 'split': 'validation'})
    poisoned.append({**poisoned[-1], 'split': 'train'})
    assert u.calibrate_rows(bundle, poisoned, trajectories) == result
    # Replicating a window must not turn 15 trajectories into 30 calibration units.
    repeated = rows[:-1] + deepcopy(rows[:-1]) + rows[-1:]
    assert u.calibrate_rows(bundle, repeated, trajectories)['radius_brix'] == result['radius_brix']
    assert u.calibrate_rows(bundle, repeated, trajectories)['trajectories'] == 15


def test_unusable_calibration_process_not_silently_dropped():
    rows, trajectories = calibration_fixture()
    for row in rows:
        if row['process_id'] == 1:
            row['eligible'] = False
    with pytest.raises(ValueError, match='no eligible forecast'):
        u.calibrate_rows({'forecaster': ConstantForecaster()}, rows, trajectories)
    with pytest.raises(ValueError):
        u.conformal_radius([float('nan')], .1)


def sample_statistics():
    rows = []
    for ident, detected in ((1, 1), (2, 0), (3, 1), (4, 0)):
        rows.append({'process_id': ident, 'scenario': 'a' if ident <= 2 else 'b',
                     **dict.fromkeys(u.STAT_NAMES, 0.), 'windows': 10., 'eligible': 8.,
                     'events': 1., 'detected': float(detected), 'forecast_n': 5.,
                     'absolute_error_sum': float(ident * 5)})
    return rows


def test_cluster_bootstrap_preserves_strata_reproducibility_and_duplicates():
    rows = sample_statistics()
    draws, strata = u.cluster_draws(rows, replicates=100, seed=3)
    assert strata == {'a': 2, 'b': 2}
    assert np.all(draws[:, :2] < 2) and np.all(draws[:, 2:] >= 2)
    np.testing.assert_array_equal(draws, u.cluster_draws(rows, 100, 3)[0])
    # Sampling a detected process twice counts two detected copies, not one ID.
    custom = np.array([[0, 0, 2, 2], [1, 1, 3, 3]])
    summary, samples = u.bootstrap_summary(rows, custom, strata)
    assert [s['event_recall_all'] for s in samples] == [1, 0]
    assert summary['point']['event_recall_all'] == .5
    assert summary['counts']['events'] == 4
    assert u.paired_difference(samples, samples)['forecast_mae_brix']['upper'] == 0


def test_undefined_metrics_and_singleton_strata_have_no_fake_intervals():
    row = sample_statistics()[0]
    draws, strata = u.cluster_draws([row], 100)
    result, _ = u.bootstrap_summary([row], draws, strata)
    assert all(r['status'] == 'not_estimable' for r in result['bootstrap_95'].values())
    assert result['bootstrap_95']['brier']['defined_replicates'] == 0
    assert result['bootstrap_95']['event_recall_all']['lower'] is None


def test_abstention_not_counted_as_coverage_and_bounds_not_clipped(monkeypatch):
    trajectories = [{'spec': {'process_id': 1, 'scenario': 'healthy'}, 'event': None},
                    {'spec': {'process_id': 2, 'scenario': 'healthy'}, 'event': None}]
    rows = [{'process_id': 1, 'eligible': True, 'forecast_target': -1},
            {'process_id': 1, 'eligible': False, 'forecast_target': 2},
            {'process_id': 2, 'eligible': False, 'forecast_target': 3}]
    def predict(*_):
        return [], [], [], [], [{'process_id': 1, 'hour': 24, 'target': -1, 'prediction': 0.}]
    monkeypatch.setattr(u, 'predict', predict)
    stats, forecasts = u.process_statistics({}, rows, trajectories, 2.)
    assert forecasts[0]['lower_brix'] == -2. and forecasts[0]['upper_brix'] == 2.
    totals = {name: sum(r[name] for r in stats) for name in u.STAT_NAMES}
    result = u.summarize(totals)
    assert result['interval_window_coverage'] == 1
    assert result['interval_availability'] == 1/3
    assert result['trajectory_emitted_coverage'] == 1
    assert result['trajectory_all_targets_served_and_covered'] == 0
    stats, forecasts = u.process_statistics({}, rows, trajectories, None)
    result = u.summarize({name: sum(r[name] for r in stats) for name in u.STAT_NAMES})
    assert result['interval_window_coverage'] is None
    assert result['interval_availability'] == 0
    assert forecasts[0]['lower_brix'] is None and forecasts[0]['covered'] is None


def test_commands_frozen_calibration_reconstruction_and_repeatability(experiment, monkeypatch):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.preprocessing import StandardScaler
    base, reference, model, stress = experiment
    before = {p.name: sha(p) for p in model.iterdir()}
    for cls in (LogisticRegression, Ridge, StandardScaler):
        monkeypatch.setattr(cls, 'fit', lambda *a, **k: pytest.fail('Uncertainty command tried to fit a model'))
    interval_dir = base / 'intervals'
    result = u.calibrate(reference, model, interval_dir)
    assert result['trajectories'] == 5 and result['radius_brix'] is None
    output = base / 'uncertainty'
    summary = u.evaluate(reference, model, interval_dir, output, stress_dataset_dir=stress, replicates=100)
    assert summary['stress_test']['latency_2h']['interval_availability'] == 0
    assert summary['stress_test']['latency_2h']['event_recall_all'] == 0
    assert summary['original_test']['clean']['interval_window_coverage'] is None
    assert {p.name: sha(p) for p in model.iterdir()} == before
    repeated = base / 'uncertainty-repeat'
    u.evaluate(reference, model, interval_dir, repeated, stress_dataset_dir=stress, replicates=100)
    assert sha(output / 'evaluation.json') == sha(repeated / 'evaluation.json')
    assert sha(output / 'forecast_intervals.json') == sha(repeated / 'forecast_intervals.json')
    with pytest.raises(FileExistsError):
        u.calibrate(reference, model, interval_dir)
    path = interval_dir / 'intervals.json'
    changed = json.loads(path.read_text())
    changed['radius_brix'] = .001
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='calibration-only reconstruction'):
        u.evaluate(reference, model, interval_dir, base / 'invalid', replicates=100)
