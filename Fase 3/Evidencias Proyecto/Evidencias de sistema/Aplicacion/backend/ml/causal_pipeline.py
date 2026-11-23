"""Offline CLI: generate -> train -> evaluate. Never imports database/config/API.

Artifacts are experimental and are never loaded by operational endpoints.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             mean_absolute_error, mean_squared_error, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services.kinetics import FEATURES, VERSION
from .causal_dataset import build_dataset, validate_partition, STRIDE_HOURS, TARGET_VERSION

STATUS = "experimental_synthetic_only_not_validated_for_real_wine"
FALSE_ALARM_BUDGET = .25


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def versions():
    backend = Path(__file__).resolve().parents[1]
    files = ("ml/causal_dataset.py", "ml/causal_pipeline.py", "app/services/kinetics.py",
             "app/simulation/model.py")
    return {"python": platform.python_version(), "code_sha256": {
        name: sha(backend / name) for name in files}, "packages": {
        p: importlib.metadata.version(p) for p in ("numpy", "scikit-learn", "pydantic", "joblib")}}


def matrix(rows):
    # Explicit allowlist: scenario, seed, event, source and future targets never enter X.
    return np.asarray([[r[name] for name in FEATURES] for r in rows], dtype=float)


def risk_rows(rows, split):
    return [r for r in rows if r["split"] == split and r["eligible"] and r["risk_target"] is not None]


def forecast_rows(rows, split):
    return [r for r in rows if r["split"] == split and r["eligible"] and r["forecast_target"] is not None]


def calibration_bins(y, probabilities):
    result = []
    for index in range(10):
        mask = (probabilities >= index / 10) & ((probabilities < (index+1) / 10)
                                                     if index < 9 else (probabilities <= 1))
        result.append({"lower": index/10, "upper": (index+1)/10, "count": int(mask.sum()),
                       "mean_probability": float(probabilities[mask].mean()) if mask.any() else None,
                       "event_frequency": float(y[mask].mean()) if mask.any() else None})
    return result


def risk_metrics(rows, probabilities, threshold):
    if not rows:
        return {"samples": 0}
    probabilities = np.asarray(probabilities, dtype=float)
    y = np.array([r["risk_target"] for r in rows])
    predicted = probabilities >= threshold
    tp, fp = int(((y == 1) & predicted).sum()), int(((y == 0) & predicted).sum())
    positives, negatives = int(y.sum()), int((y == 0).sum())
    event_processes = {r["process_id"] for r in rows if r["event_onset_hour"] is not None}
    lead_times = []
    for process_id in event_processes:
        lead = [r["event_onset_hour"] - r["hour"] for r, alarm in zip(rows, predicted)
                if r["process_id"] == process_id and r["risk_target"] == 1 and alarm]
        if lead:
            lead_times.append(max(lead))
    bins = calibration_bins(y, probabilities)
    return {"samples": len(rows), "positives": positives, "negatives": negatives,
            "threshold": threshold, "brier": float(brier_score_loss(y, probabilities)),
            "roc_auc": float(roc_auc_score(y, probabilities)) if positives and negatives else None,
            "pr_auc": float(average_precision_score(y, probabilities)) if positives and negatives else None,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/positives if positives else None,
            "false_positive_windows": fp,
            "eligible_observation_days": len(rows)*STRIDE_HOURS/24,
            "false_alarm_windows_per_day": fp/(len(rows)*STRIDE_HOURS/24),
            "events_with_eligible_history": len(event_processes), "events_detected": len(lead_times),
            "event_recall": len(lead_times)/len(event_processes) if event_processes else None,
            "median_lead_hours": float(np.median(lead_times)) if lead_times else None,
            "lead_hours": lead_times, "calibration_bins": bins,
            "ece_10_bins": sum(b["count"] * abs(b["mean_probability"] - b["event_frequency"])
                               for b in bins if b["count"])/len(rows)}


def choose_threshold(rows, probabilities):
    # Validation only. >1 is an explicit abstaining alarm policy if every
    # nonempty policy exceeds the budget. Scores remain available for evaluation.
    candidates = sorted(set([0.0, 1.000001, *map(float, probabilities)]))
    choices = []
    for threshold in candidates:
        report = risk_metrics(rows, probabilities, threshold)
        if report["false_alarm_windows_per_day"] <= FALSE_ALARM_BUDGET:
            choices.append((report["recall"] or 0, -report["false_alarm_windows_per_day"], threshold))
    return max(choices)[2]


def generate(output, **kwargs):
    output.mkdir(parents=True, exist_ok=False)
    rows, manifest = build_dataset(**kwargs)
    validate_partition(rows)
    data = output / "windows.jsonl"
    with data.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False) + "\n")
    manifest.update(status=STATUS, feature_version=VERSION, dataset_sha256=sha(data), **versions())
    write_json(output / "manifest.json", manifest)
    return {"trajectories": len(manifest["trajectories"]), "windows": len(rows),
            "events": sum(t["event"] is not None for t in manifest["trajectories"])}


def load_dataset(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["feature_version"] != VERSION or manifest["target_version"] != TARGET_VERSION
            or manifest["feature_names"] != list(FEATURES)
            or manifest["dataset_sha256"] != sha(directory / "windows.jsonl")):
        raise ValueError("Dataset hash or contract mismatch")
    rows = [json.loads(line) for line in (directory / "windows.jsonl").read_text(encoding="utf-8").splitlines()]
    validate_partition(rows)
    return rows, manifest


def calibrated_probability(bundle, rows):
    score = bundle["classifier"].decision_function(matrix(rows)).reshape(-1, 1)
    return bundle["calibrator"].predict_proba(score)[:, 1]


def train(dataset_dir, output):
    rows, manifest = load_dataset(dataset_dir)
    partitions = {s: risk_rows(rows, s) for s in ("train", "calibration", "validation")}
    for role, subset in partitions.items():
        if {r["risk_target"] for r in subset} != {0, 1}:
            raise ValueError(f"Both classes required in {role}; expand independent trajectories")
    classifier = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=42))
    classifier.fit(matrix(partitions["train"]), [r["risk_target"] for r in partitions["train"]])
    calibrator = LogisticRegression(C=1e6, max_iter=2000, random_state=42)
    calibrator.fit(classifier.decision_function(matrix(partitions["calibration"])).reshape(-1, 1),
                   [r["risk_target"] for r in partitions["calibration"]])
    forecasting = forecast_rows(rows, "train")
    forecaster = make_pipeline(StandardScaler(), Ridge(alpha=10))
    forecaster.fit(matrix(forecasting), [r["forecast_target"] for r in forecasting])
    bundle = {"classifier": classifier, "calibrator": calibrator, "forecaster": forecaster,
              "prevalence": float(np.mean([r["risk_target"] for r in partitions["train"]])),
              "features": list(FEATURES), "feature_version": VERSION, "target_version": TARGET_VERSION,
              "dataset_sha256": manifest["dataset_sha256"], "status": STATUS}
    probabilities = calibrated_probability(bundle, partitions["validation"])
    bundle["threshold"] = choose_threshold(partitions["validation"], probabilities)
    output.mkdir(parents=True, exist_ok=False)
    joblib.dump(bundle, output / "experimental.joblib")
    report = {"status": STATUS, "feature_version": VERSION, "target_version": TARGET_VERSION,
              "features": list(FEATURES), "dataset_sha256": manifest["dataset_sha256"],
              "artifact_sha256": sha(output / "experimental.joblib"),
              "threshold": bundle["threshold"], "false_alarm_budget_per_day": FALSE_ALARM_BUDGET,
              "classifier": {"type": "StandardScaler + LogisticRegression", "C": 1.0},
              "calibrator": {"type": "sigmoid logistic", "C": 1e6, "partition": "calibration"},
              "forecaster": {"type": "StandardScaler + Ridge", "alpha": 10},
              "validation": risk_metrics(partitions["validation"], probabilities, bundle["threshold"]),
              "fit_processes": {s: sorted({r["process_id"] for r in subset}) for s, subset in partitions.items()},
              **versions()}
    write_json(output / "training.json", report)
    return {"threshold": bundle["threshold"], "validation_brier": report["validation"]["brier"]}


def evaluate(dataset_dir, model_dir, output):
    rows, manifest = load_dataset(dataset_dir)
    training = json.loads((model_dir / "training.json").read_text(encoding="utf-8"))
    if training["dataset_sha256"] != manifest["dataset_sha256"]:
        raise ValueError("Model belongs to a different dataset")
    if training["artifact_sha256"] != sha(model_dir / "experimental.joblib"):
        raise ValueError("Model checksum mismatch")
    # Only load locally generated, trusted artifacts; joblib is not a safe interchange format.
    bundle = joblib.load(model_dir / "experimental.joblib")
    if bundle["features"] != list(FEATURES) or bundle["feature_version"] != VERSION:
        raise ValueError("Model feature contract mismatch")
    risk = risk_rows(rows, "test")
    forecast = forecast_rows(rows, "test")
    scores = {
        "prevalence": (np.full(len(risk), bundle["prevalence"]), .5),
        "kinetic_rule": (np.array([float(r["brix_slope_6h"] > -.015 and r["brix_slope_24h"] < -.04
                                          and r["brix_mean_1h"] > 5) for r in risk]), .5),
        "logistic_uncalibrated": (bundle["classifier"].predict_proba(matrix(risk))[:, 1], .5),
        "logistic_calibrated": (calibrated_probability(bundle, risk), bundle["threshold"]),
    }
    predictions = {"persistence": np.array([r["brix_mean_1h"] for r in forecast]),
                   "linear_6h": np.array([r["brix_mean_1h"] + 24*r["brix_slope_6h"] for r in forecast]),
                   "ridge": bundle["forecaster"].predict(matrix(forecast))}

    def metrics(risk_indices, forecast_indices):
        subset = [risk[i] for i in risk_indices]
        target = [forecast[i]["forecast_target"] for i in forecast_indices]
        return {"risk": {name: risk_metrics(subset, probability[risk_indices], threshold)
                         for name, (probability, threshold) in scores.items()},
                "forecast_24h": {name: {"samples": len(target),
                    "mae_brix": float(mean_absolute_error(target, prediction[forecast_indices])) if target else None,
                    "rmse_brix": float(np.sqrt(mean_squared_error(target, prediction[forecast_indices]))) if target else None}
                    for name, prediction in predictions.items()}}

    report = {"status": STATUS, "dataset_sha256": manifest["dataset_sha256"],
              "artifact_sha256": training["artifact_sha256"], "source": "simulado",
              "target_version": TARGET_VERSION, "feature_version": VERSION,
              "horizon_hours": 12, "minimum_lead_hours": 2, "forecast_hours": 24,
              "false_alarm_unit": "positive windows on negatives / eligible risk observation days",
              "test_trajectories": [t for t in manifest["trajectories"] if t["split"] == "test"],
              "coverage": {"total_test_windows": sum(r["split"] == "test" for r in rows),
                           "feature_eligible": sum(r["split"] == "test" and r["eligible"] for r in rows),
                           "risk_evaluated": len(risk), "forecast_evaluated": len(forecast)},
              "overall": metrics(list(range(len(risk))), list(range(len(forecast)))),
              "by_scenario": {}, "by_process": {}, **versions()}
    for key, field in (("by_scenario", "scenario"), ("by_process", "process_id")):
        for value in sorted({r[field] for r in rows if r["split"] == "test"}):
            report[key][str(value)] = metrics([i for i, r in enumerate(risk) if r[field] == value],
                                             [i for i, r in enumerate(forecast) if r[field] == value])
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "evaluation.json", report)
    write_json(output / "risk_predictions.json", [
        {"process_id": r["process_id"], "hour": r["hour"], "target": r["risk_target"],
         **{name: float(p[i]) for name, (p, _) in scores.items()}} for i, r in enumerate(risk)])
    write_json(output / "forecast_predictions.json", [
        {"process_id": r["process_id"], "hour": r["hour"], "target": r["forecast_target"],
         **{name: float(p[i]) for name, p in predictions.items()}} for i, r in enumerate(forecast)])
    return report["overall"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate")
    gen.add_argument("--output-dir", required=True, type=Path)
    gen.add_argument("--seed", type=int, default=2026)
    gen.add_argument("--per-scenario", type=int, default=20)
    gen.add_argument("--duration-hours", type=int, default=240)
    for command in ("train", "evaluate"):
        sub = commands.add_parser(command)
        sub.add_argument("--dataset-dir", required=True, type=Path)
        sub.add_argument("--output-dir", required=True, type=Path)
        if command == "evaluate":
            sub.add_argument("--model-dir", required=True, type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    args["output"] = args.pop("output_dir")
    result = {"generate": generate, "train": train, "evaluate": evaluate}[command](**args)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
