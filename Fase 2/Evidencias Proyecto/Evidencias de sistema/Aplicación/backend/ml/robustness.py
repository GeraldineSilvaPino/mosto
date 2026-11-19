"""Paired offline fault stress tests of a frozen model; no fit, DB or network."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import random

import joblib
import numpy as np

from app.services.kinetics import FEATURES, VERSION, Observation, extract
from app.simulation.model import SCENARIOS, SimulationSpec, Trajectory
from .causal_dataset import START, STRIDE_HOURS, TARGET_VERSION, first_event, risk_label
from .causal_pipeline import (STATUS, calibrated_probability, load_dataset, matrix,
                              risk_metrics, sha, versions, write_json)

CONTRACT = "sensor-stress-v1"
# Fixed before looking at the held-out results. Faults do not alter biology/targets.
POLICIES = {
    "clean": {"duration_hours": 0},
    "brix_missing": {"duration_hours": 12},
    "temperature_missing": {"duration_hours": 12},
    "brix_frozen_unflagged": {"duration_hours": 24},
    "brix_drift_unflagged": {"duration_hours": 48, "drift_brix_per_hour": .08},
    "communication_loss": {"duration_hours": 12},
    "delivery_backlog": {"duration_hours": 12, "release_delay_minutes": 5},
    "latency_2h": {"delay_hours": 2},
}


def reference(dataset_dir, model_dir):
    _, manifest = load_dataset(dataset_dir)
    training = json.loads((model_dir / "training.json").read_text(encoding="utf-8"))
    artifact = sha(model_dir / "experimental.joblib")
    if training["artifact_sha256"] != artifact or training["dataset_sha256"] != manifest["dataset_sha256"]:
        raise ValueError("Reference model/dataset checksum mismatch")
    if (training["feature_version"] != VERSION or training["target_version"] != TARGET_VERSION
            or training["features"] != list(FEATURES) or training["status"] != STATUS):
        raise ValueError("Reference model contract mismatch")
    current = versions()
    for name in ("app/services/kinetics.py", "app/simulation/model.py", "ml/causal_dataset.py"):
        if manifest["code_sha256"][name] != current["code_sha256"][name]:
            raise ValueError("Reference generator/extractor code changed; preserve experiment version")
    return manifest, training


def reserved_specs(manifest, seed=20261117, per_scenario=4, duration_hours=240):
    if not 1 <= per_scenario <= 100 or not 120 <= duration_hours <= 720:
        raise ValueError("Use 1..100 trajectories per scenario and 120..720 hours")
    rng = random.Random(seed)
    used = {t["spec"]["seed"] for t in manifest["trajectories"]}
    first_id = max(t["spec"]["process_id"] for t in manifest["trajectories"]) + 1
    result = []
    for scenario in SCENARIOS:
        for _ in range(per_scenario):
            sample_seed = rng.randrange(1, 2147483647)
            while sample_seed in used:
                sample_seed = rng.randrange(1, 2147483647)
            used.add(sample_seed)
            spec = SimulationSpec(process_id=first_id + len(result), process_start=START,
                seed=sample_seed, scenario=scenario, duration_hours=duration_hours,
                initial_brix=rng.uniform(21, 27), ambient_c=rng.uniform(19, 25),
                fault_at_hours=rng.uniform(40, min(100, duration_hours - 12)))
            # Independent of latent event time and of the fermentation fault.
            sensor_fault_start = rng.randint(48, min(96, duration_hours - 24))
            result.append((spec, sensor_fault_start))
    return result


def perturb(observations, policy, start_hour):
    """Pure observation-layer faults. Keep observation time; delay only receipt."""
    config = POLICIES[policy]
    if policy == "clean":
        return list(observations)
    start = START + timedelta(hours=start_hour)
    end = start + timedelta(hours=config.get("duration_hours", 0))
    anchor = next((row.brix for row in reversed(observations) if row.observed_at < start), None)
    if policy == "brix_frozen_unflagged" and anchor is None:
        raise ValueError("Frozen sensor requires a previous sample")
    result = []
    for row in observations:
        if policy == "latency_2h":
            row = replace(row, received_at=row.received_at + timedelta(hours=config["delay_hours"]))
        elif start <= row.observed_at < end:
            if policy == "communication_loss":
                continue
            if policy == "delivery_backlog":
                row = replace(row, received_at=max(row.received_at,
                    end + timedelta(minutes=config["release_delay_minutes"])))
            elif policy == "brix_missing":
                row = replace(row, brix=None, brix_quality="missing")
            elif policy == "temperature_missing":
                row = replace(row, temperature=None, temperature_quality="missing")
            elif policy == "brix_frozen_unflagged":
                row = replace(row, brix=anchor)
            elif policy == "brix_drift_unflagged":
                hours = (row.observed_at - start).total_seconds() / 3600
                row = replace(row, brix=None if row.brix is None else
                              row.brix + hours * config["drift_brix_per_hour"])
        result.append(row)
    return result


def windows(spec, samples, observations, event, policy, start_hour):
    config = POLICIES[policy]
    affected_end = start_hour + config.get("duration_hours", 0) + 24
    for hour in range(24, spec.duration_hours + 1, STRIDE_HOURS):
        cutoff = START + timedelta(hours=hour)
        # Bound by observation time only. The shared extractor enforces receipt.
        past = [row for row in observations if cutoff - timedelta(hours=24) <= row.observed_at <= cutoff]
        result = extract(past, process_id=spec.process_id, process_start=START, as_of=cutoff)
        label, reason = risk_label(hour, event, spec.duration_hours)
        yield {"process_id": spec.process_id, "seed": spec.seed, "scenario": spec.scenario,
               "policy": policy, "hour": hour, "as_of": cutoff.isoformat(),
               "exposed": policy == "latency_2h" or (policy != "clean" and start_hour <= hour <= affected_end),
               "eligible": result["eligible"], "abstention_reasons": result["abstention_reasons"],
               "channels": result["channels"], "risk_target": label, "risk_exclusion": reason,
               # Always the clean observed future, never a corrupted sensor target.
               "forecast_target": samples[(hour + 24)*12]["brix_apparent"] if hour + 24 <= spec.duration_hours else None,
               "event_onset_hour": event["onset_hour"] if event else None, **result["features"]}


def generate(reference_dataset_dir, model_dir, output, seed=20261117, per_scenario=4, duration_hours=240):
    manifest, training = reference(reference_dataset_dir, model_dir)
    output.mkdir(parents=True, exist_ok=False)
    trajectories = []
    count = 0
    with (output / "windows.jsonl").open("x", encoding="utf-8") as handle:
        for spec, start in reserved_specs(manifest, seed, per_scenario, duration_hours):
            trajectory = Trajectory(spec)
            samples = [trajectory.sample(i) for i in range(duration_hours*12 + 1)]
            observations = [Observation(spec.process_id, START + timedelta(minutes=5*i),
                START + timedelta(minutes=5*i), sample["brix_apparent"], sample["temperature_c"],
                calibration_id=spec.process_id) for i, sample in enumerate(samples)]
            event = first_event([s["latent_brix"] for s in samples[::12]], spec.asymptote_brix)
            trajectories.append({"spec": spec.model_dump(mode="json"), "event": event, "sensor_fault_start_hour": start})
            for policy in POLICIES:
                for row in windows(spec, samples, perturb(observations, policy, start), event, policy, start):
                    handle.write(json.dumps(row, allow_nan=False) + "\n")
                    count += 1
    write_json(output / "manifest.json", {
        "contract": CONTRACT, "status": STATUS, "feature_version": VERSION, "target_version": TARGET_VERSION,
        "feature_names": list(FEATURES), "generation_seed": seed, "policies": POLICIES,
        "per_scenario": per_scenario, "duration_hours": duration_hours, "stride_hours": STRIDE_HOURS,
        "reference_dataset_sha256": manifest["dataset_sha256"],
        "frozen_artifact_sha256": training["artifact_sha256"], "frozen_threshold": training["threshold"],
        "dataset_sha256": sha(output / "windows.jsonl"), "trajectories": trajectories,
        "robustness_code_sha256": sha(Path(__file__)), **versions()})
    return {"trajectories": len(trajectories), "policies": len(POLICIES), "windows": count}


def load_stress(directory, reference_manifest, training):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["contract"] != CONTRACT or manifest["policies"] != POLICIES
            or manifest["feature_version"] != VERSION or manifest["target_version"] != TARGET_VERSION
            or manifest["feature_names"] != list(FEATURES)
            or manifest["stride_hours"] != STRIDE_HOURS
            or manifest["reference_dataset_sha256"] != reference_manifest["dataset_sha256"]
            or manifest["frozen_artifact_sha256"] != training["artifact_sha256"]
            or manifest["frozen_threshold"] != training["threshold"]
            or manifest["robustness_code_sha256"] != sha(Path(__file__))
            or manifest["dataset_sha256"] != sha(directory / "windows.jsonl")):
        raise ValueError("Stress dataset/model/contract checksum mismatch")
    rows = [json.loads(line) for line in (directory / "windows.jsonl").read_text(encoding="utf-8").splitlines()]
    originals = {t["spec"]["seed"] for t in reference_manifest["trajectories"]}
    original_ids = {t["spec"]["process_id"] for t in reference_manifest["trajectories"]}
    trajectories = {t["spec"]["process_id"]: t for t in manifest["trajectories"]}
    if len(trajectories) != len(manifest["trajectories"]) or len({t["spec"]["seed"] for t in trajectories.values()}) != len(trajectories):
        raise ValueError("Duplicate held-out trajectory or seed")
    if not trajectories:
        raise ValueError("No held-out trajectories")
    if original_ids.intersection(trajectories) or originals.intersection(t["spec"]["seed"] for t in trajectories.values()):
        raise ValueError("Stress trajectories overlap original experiment")
    expected = {(ident, policy, hour) for ident, t in trajectories.items() for policy in POLICIES
                for hour in range(24, t["spec"]["duration_hours"] + 1, STRIDE_HOURS)}
    keys = [(r["process_id"], r["policy"], r["hour"]) for r in rows]
    if len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError("Missing, extra or duplicate paired windows")
    clean = {(r["process_id"], r["hour"]): r for r in rows if r["policy"] == "clean"}
    for row in rows:
        trajectory = trajectories[row["process_id"]]
        if row["seed"] != trajectory["spec"]["seed"] or row["scenario"] != trajectory["spec"]["scenario"]:
            raise ValueError("Trajectory identity mismatch")
        label, reason = risk_label(row["hour"], trajectory["event"], trajectory["spec"]["duration_hours"])
        onset = trajectory["event"]["onset_hour"] if trajectory["event"] else None
        if (row["risk_target"], row["risk_exclusion"], row["event_onset_hour"]) != (label, reason, onset):
            raise ValueError("Risk targets do not match trajectory event")
        baseline = clean[(row["process_id"], row["hour"])]
        if any(row[key] != baseline[key] for key in ("risk_target", "risk_exclusion", "forecast_target", "event_onset_hour")):
            raise ValueError("Observation fault changed clean targets")
        if row["eligible"] and any(row[f] is None or not np.isfinite(row[f]) for f in FEATURES):
            raise ValueError("Nonfinite eligible features")
    return rows, manifest


def predict(bundle, rows):
    risk = [r for r in rows if r["eligible"] and r["risk_target"] is not None]
    forecast = [r for r in rows if r["eligible"] and r["forecast_target"] is not None]
    probabilities = calibrated_probability(bundle, risk) if risk else np.array([])
    forecasts = bundle["forecaster"].predict(matrix(forecast)) if forecast else np.array([])
    risk_predictions = [{"process_id": r["process_id"], "hour": r["hour"],
        "target": r["risk_target"], "probability": float(p), "alarm": bool(p >= bundle["threshold"])}
        for r, p in zip(risk, probabilities)]
    forecast_predictions = [{"process_id": r["process_id"], "hour": r["hour"],
        "target": r["forecast_target"], "prediction": float(p)} for r, p in zip(forecast, forecasts)]
    return risk, forecast, probabilities, risk_predictions, forecast_predictions


def metrics(bundle, rows, trajectories):
    risk, forecast, probabilities, rp, fp = predict(bundle, rows)
    target_rows = [r for r in rows if r["risk_target"] is not None]
    events = {t["spec"]["process_id"] for t in trajectories if t["event"] is not None}
    opportunity = {r["process_id"] for r in rows if r["risk_target"] == 1}
    eligible_opportunity = {r["process_id"] for r in risk if r["risk_target"] == 1}
    detected = {r["process_id"] for r in rp if r["target"] == 1 and r["alarm"]}
    errors = np.array([r["prediction"] - r["target"] for r in fp])
    baseline_errors = np.array([r["brix_mean_1h"] - r["forecast_target"] for r in forecast])
    report = {
        "coverage": {"windows": len(rows), "eligible": sum(r["eligible"] for r in rows),
            "abstentions": sum(not r["eligible"] for r in rows),
            "abstention_rate": sum(not r["eligible"] for r in rows)/len(rows) if rows else None,
            "reasons": dict(Counter(reason for r in rows for reason in r["abstention_reasons"])),
            "risk_target_windows": len(target_rows), "risk_scored": len(risk),
            "forecast_target_windows": sum(r["forecast_target"] is not None for r in rows),
            "forecast_scored": len(forecast)},
        "risk": risk_metrics(risk, probabilities, bundle["threshold"]),
        "event_detection": {"total_events": len(events), "events_with_warning_opportunity": len(events & opportunity),
            "events_with_eligible_warning": len(events & eligible_opportunity), "detected": len(events & detected),
            "recall_all_events": len(events & detected)/len(events) if events else None,
            "undetected_process_ids": sorted(events - detected)},
        "forecast_24h": {"samples": len(fp), "target": "uncorrupted_observed_brix_at_24h",
            "ridge_mae_brix": float(np.abs(errors).mean()) if len(errors) else None,
            "ridge_rmse_brix": float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
            "persistence_mae_brix": float(np.abs(baseline_errors).mean()) if len(errors) else None},
    }
    return report, rp, fp


def paired_metrics(clean_risk, clean_forecast, risk, forecast):
    cr = {(r["process_id"], r["hour"]): r for r in clean_risk}
    cf = {(r["process_id"], r["hour"]): r for r in clean_forecast}
    common_risk = [(cr[(r["process_id"], r["hour"])], r) for r in risk if (r["process_id"], r["hour"]) in cr]
    common_forecast = [(cf[(r["process_id"], r["hour"])], r) for r in forecast if (r["process_id"], r["hour"]) in cf]
    def avg(values):
        return float(np.mean(values)) if values else None
    return {"common_risk_windows": len(common_risk),
            "mean_absolute_probability_change": avg([abs(a["probability"] - b["probability"]) for a, b in common_risk]),
            "alarm_flips": sum(a["alarm"] != b["alarm"] for a, b in common_risk),
            "common_forecast_windows": len(common_forecast),
            "clean_mae_on_common": avg([abs(a["prediction"] - a["target"]) for a, b in common_forecast]),
            "fault_mae_on_common": avg([abs(b["prediction"] - b["target"]) for a, b in common_forecast])}


def evaluate(dataset_dir, reference_dataset_dir, model_dir, output):
    reference_manifest, training = reference(reference_dataset_dir, model_dir)
    rows, manifest = load_stress(dataset_dir, reference_manifest, training)
    # Only locally generated trusted joblib, after checksum/contract verification.
    bundle = joblib.load(model_dir / "experimental.joblib")
    if (bundle["features"] != list(FEATURES) or bundle["feature_version"] != VERSION
            or bundle["target_version"] != TARGET_VERSION or bundle["threshold"] != training["threshold"]
            or bundle["dataset_sha256"] != reference_manifest["dataset_sha256"] or bundle["status"] != STATUS):
        raise ValueError("Frozen bundle contract mismatch")
    report = {"contract": CONTRACT, "status": STATUS, "frozen_threshold": bundle["threshold"],
        "artifact_sha256": training["artifact_sha256"], "dataset_sha256": manifest["dataset_sha256"],
        "reference_dataset_sha256": reference_manifest["dataset_sha256"],
        "trajectories": len(manifest["trajectories"]), "policies": {},
        "false_alarm_unit": "positive windows on negatives / eligible risk observation days",
        "notes": ["No refit, recalibration, threshold selection or promotion.",
                  "Paired variants are not independent trajectories; metrics are descriptive, without confidence intervals.",
                  "All-event recall includes abstentions; conditional metrics use scored windows only.",
                  "New sensor/transport mechanisms on the same biological simulator, not real-world validation."],
        "robustness_code_sha256": sha(Path(__file__)), **versions()}
    predictions = {}
    for policy in POLICIES:
        subset = [r for r in rows if r["policy"] == policy]
        summary, risk, forecast = metrics(bundle, subset, manifest["trajectories"])
        summary["by_scenario"] = {scenario: metrics(bundle, [r for r in subset if r["scenario"] == scenario],
            [t for t in manifest["trajectories"] if t["spec"]["scenario"] == scenario])[0] for scenario in SCENARIOS}
        # Exposed windows include the past-24h footprint, not only the fault's active samples.
        exposed = [r for r in subset if r["exposed"]]
        exposed_report = metrics(bundle, exposed, manifest["trajectories"])[0]
        summary["exposed_windows"] = {key: exposed_report[key] for key in ("coverage", "risk", "forecast_24h")}
        summary["by_process"] = {str(t["spec"]["process_id"]): metrics(bundle,
            [r for r in subset if r["process_id"] == t["spec"]["process_id"]], [t])[0]
            for t in manifest["trajectories"]}
        predictions[policy] = {"risk": risk, "forecast": forecast}
        report["policies"][policy] = summary
    clean = predictions["clean"]
    for policy, prediction in predictions.items():
        report["policies"][policy]["paired_with_clean"] = paired_metrics(
            clean["risk"], clean["forecast"], prediction["risk"], prediction["forecast"])
    if sha(model_dir / "experimental.joblib") != training["artifact_sha256"]:
        raise ValueError("Frozen model changed during evaluation")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "evaluation.json", report)
    write_json(output / "predictions.json", predictions)
    return {policy: {"abstention_rate": r["coverage"]["abstention_rate"],
                    "event_recall": r["event_detection"]["recall_all_events"],
                    "ridge_mae_brix": r["forecast_24h"]["ridge_mae_brix"]} for policy, r in report["policies"].items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--reference-dataset-dir", required=True, type=Path)
        sub.add_argument("--model-dir", required=True, type=Path)
        sub.add_argument("--output-dir", required=True, type=Path)
        if name == "generate":
            sub.add_argument("--seed", type=int, default=20261117)
            sub.add_argument("--per-scenario", type=int, default=4)
            sub.add_argument("--duration-hours", type=int, default=240)
        else:
            sub.add_argument("--dataset-dir", required=True, type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    args["output"] = args.pop("output_dir")
    print(json.dumps({"generate": generate, "evaluate": evaluate}[command](**args), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
