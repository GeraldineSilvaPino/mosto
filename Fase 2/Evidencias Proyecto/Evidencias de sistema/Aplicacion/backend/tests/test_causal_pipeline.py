from copy import deepcopy
import json

import joblib
import numpy as np
import pytest

from app.services.kinetics import FEATURES
from ml.causal_dataset import first_event, risk_label, specs, validate_partition
from ml.causal_pipeline import (choose_threshold, evaluate, generate, load_dataset,
                                matrix, risk_metrics, sha, train)


def test_event_requires_future_persistence_prior_activity_and_remaining_level():
    curve = [24 - .1*h for h in range(60)] + [18.1] * 30
    event = first_event(curve, -1)
    assert event == {"onset_hour": 59, "confirmed_hour": 65}
    assert first_event([24] * 100, -1) is None  # lag without established activity
    assert first_event([max(1, 24-h) for h in range(100)], -1) is None  # normal end
    assert first_event(curve[:64], -1) is None  # cannot confirm incomplete persistence


@pytest.mark.parametrize("hour,followup,expected", [
    (47, 100, (1, None)), (48, 100, (1, None)), (57, 100, (None, "insufficient_lead")),
    (59, 100, (None, "event_already_started")), (46, 100, (0, None)),
    (47, 64, (None, "right_censored")),
])
def test_future_target_boundaries_and_censoring(hour, followup, expected):
    assert risk_label(hour, {"onset_hour": 59, "confirmed_hour": 65}, followup) == expected
    assert risk_label(90, None, 100) == (None, "right_censored")


def test_independent_seeds_and_reproducible_full_trajectory_specs():
    first = specs(per_scenario=8)
    assert first == specs(per_scenario=8)
    assert len({s.seed for _, s in first}) == len(first)
    assert {split for split, _ in first} == {"train", "calibration", "validation", "test"}
    for scenario in {s.scenario for _, s in first}:
        assert {split for split, s in first if s.scenario == scenario} == {
            "train", "calibration", "validation", "test"}


def test_feature_allowlist_cannot_ingest_provenance_or_future():
    row = dict.fromkeys(FEATURES, 1.)
    poisoned = {**row, "scenario": "secret", "seed": 123, "event_onset_hour": -999,
                "risk_target": 1, "forecast_target": 999, "viability": 0}
    np.testing.assert_array_equal(matrix([row]), matrix([poisoned]))


def test_metrics_missing_class_and_threshold_budget_are_explicit():
    rows = [{"process_id": 1, "hour": h, "event_onset_hour": None, "risk_target": 0}
            for h in range(10)]
    report = risk_metrics(rows, np.full(10, .4), .5)
    assert report["roc_auc"] is None and report["pr_auc"] is None
    assert report["recall"] is None and report["event_recall"] is None
    assert report["median_lead_hours"] is None
    threshold = choose_threshold(rows, np.ones(10))
    assert threshold > 1


def test_offline_pipeline_and_holdout_cannot_change_fitted_model(tmp_path):
    dataset, model, report = (tmp_path / name for name in ("dataset", "model", "report"))
    summary = generate(dataset, seed=2026, per_scenario=8, duration_hours=120)
    assert summary["trajectories"] == 40 and summary["events"] > 0
    rows, manifest = load_dataset(dataset)
    validate_partition(rows)
    overlapping = deepcopy(rows)
    overlapping[0]["split"] = "test"
    with pytest.raises(ValueError, match="Process|Seed"):
        validate_partition(overlapping)
    reused_seed = deepcopy(rows)
    other_seed = next(r["seed"] for r in rows if r["process_id"] != rows[0]["process_id"])
    for row in reused_seed:
        if row["process_id"] == rows[0]["process_id"]:
            row["seed"] = other_seed
    with pytest.raises(ValueError, match="Seed"):
        validate_partition(reused_seed)
    train(dataset, model)
    result = evaluate(dataset, model, report)
    assert result["risk"]["logistic_calibrated"]["samples"] > 0
    assert result["forecast_24h"]["ridge"]["samples"] > 0
    assert {t["split"] for t in json.loads((report/"evaluation.json").read_text())["test_trajectories"]} == {"test"}

    # Adversarial held-out labels and features must not affect training, scaling,
    # calibration or threshold selection. Rehash an intentionally modified fixture.
    for row in rows:
        if row["split"] == "test":
            row.update({name: 999 for name in FEATURES})
            row["risk_target"] = 1
            row["forecast_target"] = -999
    (dataset / "windows.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    manifest["dataset_sha256"] = sha(dataset / "windows.jsonl")
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    changed = tmp_path / "changed"
    train(dataset, changed)
    original = joblib.load(model / "experimental.joblib")
    new = joblib.load(changed / "experimental.joblib")
    assert new["threshold"] == original["threshold"]
    x = matrix([r for r in rows if r["split"] == "train"])
    np.testing.assert_array_equal(original["classifier"].predict_proba(x), new["classifier"].predict_proba(x))
    np.testing.assert_array_equal(original["forecaster"].predict(x), new["forecaster"].predict(x))
    np.testing.assert_array_equal(original["calibrator"].coef_, new["calibrator"].coef_)
    with pytest.raises(ValueError, match="different dataset"):
        evaluate(dataset, model, tmp_path / "mismatch")
    with pytest.raises(FileExistsError):
        generate(dataset, per_scenario=8, duration_hours=120)
