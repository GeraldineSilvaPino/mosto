from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import numpy as np
import pytest

from app.services.kinetics import Observation, extract
from ml.causal_dataset import START
from ml import robustness as stress
from ml.causal_pipeline import generate as generate_reference, train, sha


def observations():
    return [Observation(1, START + timedelta(minutes=5*i), START + timedelta(minutes=5*i),
                        24 - i/120, 22, calibration_id=1) for i in range(100*12 + 1)]


def features(rows, hour):
    return extract(rows, process_id=1, process_start=START, as_of=START + timedelta(hours=hour))


def test_reserved_recipes_are_reproducible_disjoint_and_paired():
    manifest = {"trajectories": [{"spec": {"seed": 123, "process_id": 9}}]}
    result = stress.reserved_specs(manifest, per_scenario=2, duration_hours=120)
    assert result == stress.reserved_specs(manifest, per_scenario=2, duration_hours=120)
    assert len(result) == 10
    assert len({s.seed for s, _ in result}) == 10
    assert all(s.seed != 123 and s.process_id > 9 and 48 <= hour <= 96 for s, hour in result)
    with pytest.raises(ValueError):
        stress.reserved_specs(manifest, per_scenario=0)


def test_channel_failure_and_temporal_gap_are_not_healthy_data():
    clean = observations()
    brix = stress.perturb(clean, 'brix_missing', 48)
    temp = stress.perturb(clean, 'temperature_missing', 48)
    assert clean[48*12].brix is not None and clean[48*12].temperature == 22
    b = features(brix, 54)
    t = features(temp, 54)
    assert not b['eligible'] and b['features']['brix_mean_1h'] is None
    assert b['features']['temperature_mean_1h'] == 22
    assert not t['eligible'] and t['features']['brix_mean_1h'] is not None
    assert t['features']['temperature_mean_1h'] is None
    lost = stress.perturb(clean, 'communication_loss', 48)
    assert len(lost) == len(clean) - 12*12
    assert not features(lost, 54)['eligible']
    assert features(lost, 87)['eligible']  # enough uncontaminated history again


def test_delayed_messages_cannot_enter_before_receipt_and_backlog_recovers():
    clean = observations()
    delayed = stress.perturb(clean, 'delivery_backlog', 48)
    end = START + timedelta(hours=60, minutes=5)
    assert delayed[48*12].observed_at == clean[48*12].observed_at
    assert delayed[48*12].received_at == end
    for hour in (51, 57, 60):
        cutoff = START + timedelta(hours=hour)
        available = [r for r in delayed if r.received_at <= cutoff]
        assert features(delayed, hour) == features(available, hour)
        assert not features(delayed, hour)['eligible']
    # Once the backlog actually arrives it can support the next causal window.
    assert features(delayed, 63)['features'] == features(clean, 63)['features']
    assert features(delayed, 63)['eligible']
    late = stress.perturb(clean, 'latency_2h', 48)
    assert not features(late, 90)['eligible']
    assert features(late, 90)['channels']['brix']['latest_age_seconds'] == 7200


def test_unflagged_freeze_and_drift_remain_eligible_exposing_detector_limit():
    clean = observations()
    freeze = stress.perturb(clean, 'brix_frozen_unflagged', 48)
    drift = stress.perturb(clean, 'brix_drift_unflagged', 48)
    assert freeze[48*12].brix == clean[48*12-1].brix
    assert len({r.brix for r in freeze[48*12:72*12]}) == 1
    assert all(r.brix_quality == 'good' for r in freeze)
    assert features(freeze, 60)['eligible']
    assert abs(features(freeze, 60)['features']['brix_slope_6h']) < 1e-10
    assert features(drift, 60)['eligible']
    assert drift[60*12].brix == pytest.approx(clean[60*12].brix + .96)
    # A future change cannot leak backwards into any feature.
    poisoned = [replace(r, brix=999) if r.observed_at > START + timedelta(hours=60) else r for r in drift]
    assert features(drift, 60) == features(poisoned, 60)


def test_empty_scores_keep_event_denominator_and_never_call_models():
    row = {'process_id': 7, 'risk_target': 1, 'forecast_target': 20,
           'eligible': False, 'abstention_reasons': ['brix_stale']}
    report, risk, forecast = stress.metrics({'threshold': .5}, [row],
        [{'spec': {'process_id': 7}, 'event': {'onset_hour': 60}}])
    assert report['coverage']['abstention_rate'] == 1
    assert report['risk'] == {'samples': 0}
    assert report['event_detection']['total_events'] == 1
    assert report['event_detection']['events_with_warning_opportunity'] == 1
    assert report['event_detection']['events_with_eligible_warning'] == 0
    assert report['event_detection']['recall_all_events'] == 0
    assert report['forecast_24h']['ridge_mae_brix'] is None
    assert risk == forecast == []


@pytest.fixture(scope='module')
def experiment(tmp_path_factory):
    base = tmp_path_factory.mktemp('robustness')
    reference, model, dataset = (base / name for name in ('reference', 'model', 'stress'))
    generate_reference(reference, per_scenario=8, duration_hours=120)
    train(reference, model)
    stress.generate(reference, model, dataset, per_scenario=1, duration_hours=120)
    return base, reference, model, dataset


def test_offline_frozen_pipeline_preserves_targets_and_never_fits(experiment, monkeypatch):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.preprocessing import StandardScaler
    base, reference, model, dataset = experiment
    before = {p.name: sha(p) for p in model.iterdir()}
    manifest, training = stress.reference(reference, model)
    rows, metadata = stress.load_stress(dataset, manifest, training)
    assert len(rows) == 5*8*33
    assert len(metadata['trajectories']) == 5
    clean = {(r['process_id'], r['hour']): r for r in rows if r['policy'] == 'clean'}
    for row in rows:
        assert row['forecast_target'] == clean[(row['process_id'], row['hour'])]['forecast_target']
    for cls in (LogisticRegression, Ridge, StandardScaler):
        monkeypatch.setattr(cls, 'fit', lambda *a, **k: pytest.fail('Stress evaluation tried to fit'))
    output = base / 'evaluation'
    summary = stress.evaluate(dataset, reference, model, output)
    assert summary['latency_2h']['abstention_rate'] == 1
    assert summary['latency_2h']['ridge_mae_brix'] is None
    assert summary['clean']['abstention_rate'] == 0
    assert {p.name: sha(p) for p in model.iterdir()} == before
    report = json.loads((output / 'evaluation.json').read_text())
    assert report['frozen_threshold'] == training['threshold']
    assert report['policies']['clean']['paired_with_clean']['alarm_flips'] == 0
    assert report['policies']['brix_missing']['coverage']['abstentions'] > 0
    assert report['policies']['brix_frozen_unflagged']['coverage']['abstentions'] == 0
    with pytest.raises(FileExistsError):
        stress.evaluate(dataset, reference, model, output)


def test_corrupted_manifest_overlap_missing_pairs_and_targets_rejected(experiment, tmp_path):
    _, reference, model, dataset = experiment
    original = json.loads((dataset / 'manifest.json').read_text())
    manifest, training = stress.reference(reference, model)
    original_rows = [json.loads(line) for line in (dataset / 'windows.jsonl').read_text().splitlines()]

    def write(rows, metadata):
        data = tmp_path / 'windows.jsonl'
        data.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
        metadata['dataset_sha256'] = sha(data)
        (tmp_path / 'manifest.json').write_text(json.dumps(metadata), encoding='utf-8')

    changed = deepcopy(original)
    changed['trajectories'][0]['spec']['seed'] = manifest['trajectories'][0]['spec']['seed']
    write(original_rows, changed)
    with pytest.raises(ValueError, match='overlap'):
        stress.load_stress(tmp_path, manifest, training)
    write(original_rows[:-1], deepcopy(original))
    with pytest.raises(ValueError, match='paired windows'):
        stress.load_stress(tmp_path, manifest, training)
    changed_rows = deepcopy(original_rows)
    changed_rows[-2]['forecast_target'] = 999
    write(changed_rows, deepcopy(original))
    with pytest.raises(ValueError, match='changed clean targets'):
        stress.load_stress(tmp_path, manifest, training)
    write(original_rows, deepcopy(original))
    bad_training = {**training, 'threshold': -1}
    with pytest.raises(ValueError, match='checksum mismatch'):
        stress.load_stress(tmp_path, manifest, bad_training)
    with (tmp_path / 'windows.jsonl').open('a') as handle:
        handle.write('corruption')
    with pytest.raises(ValueError, match='checksum mismatch'):
        stress.load_stress(tmp_path, manifest, training)


def test_generation_reproducible_and_refuses_overwrite(experiment):
    base, reference, model, dataset = experiment
    repeat = base / 'repeat'
    stress.generate(reference, model, repeat, per_scenario=1, duration_hours=120)
    assert sha(repeat / 'windows.jsonl') == sha(dataset / 'windows.jsonl')
    assert sha(repeat / 'manifest.json') == sha(dataset / 'manifest.json')
    with pytest.raises(FileExistsError):
        stress.generate(reference, model, repeat)
