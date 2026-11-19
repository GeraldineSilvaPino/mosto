"""Complete independent trajectories, future labels, and shared causal features."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import random

from app.services.kinetics import FEATURES, Observation, extract
from app.simulation.model import MODEL_VERSION, SCENARIOS, SimulationSpec, Trajectory

TARGET_VERSION = "future-stall-v1"
HORIZON_HOURS = 12
MIN_LEAD_HOURS = 2
PERSISTENCE_HOURS = 6
FORECAST_HOURS = 24
STRIDE_HOURS = 3
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def first_event(latent_brix, asymptote):
    """Hourly adjudication; onset is not the later confirmation time.

    No scenario/latent phase/viability is used to decide the target. Future
    latent values are only ground truth for this synthetic experiment.
    """
    for hour in range(24, len(latent_brix) - PERSISTENCE_HOURS):
        window = latent_brix[hour:hour + PERSISTENCE_HOURS + 1]
        if (latent_brix[0] - window[0] >= 1 and min(window) - asymptote > 5
                and all(0 <= a - b <= .01 for a, b in zip(window, window[1:]))):
            return {"onset_hour": hour, "confirmed_hour": hour + PERSISTENCE_HOURS}
    return None


def risk_label(hour, event, followup_hours):
    if hour + HORIZON_HOURS + PERSISTENCE_HOURS > followup_hours:
        return None, "right_censored"
    if event:
        delta = event["onset_hour"] - hour
        if delta <= 0:
            return None, "event_already_started"
        if delta <= MIN_LEAD_HOURS:
            return None, "insufficient_lead"
        return int(delta <= HORIZON_HOURS), None
    return 0, None


def specs(seed=2026, per_scenario=20, duration_hours=240):
    if per_scenario < 8:
        raise ValueError("At least eight trajectories per scenario required for four disjoint splits")
    if not 120 <= duration_hours <= 720:
        raise ValueError("Dataset duration must be between 120 and 720 hours")
    rng = random.Random(seed)
    # Each seed is used once, including across scenarios and split roles.
    seeds = rng.sample(range(1, 2147483647), per_scenario * len(SCENARIOS))
    counts = [int(per_scenario * .55), max(1, int(per_scenario * .15)),
              max(1, int(per_scenario * .15))]
    roles = (["train"] * counts[0] + ["calibration"] * counts[1]
             + ["validation"] * counts[2])
    roles += ["test"] * (per_scenario - len(roles))
    result = []
    for scenario in SCENARIOS:
        for role in roles:
            process_id = len(result) + 1
            spec = SimulationSpec(process_id=process_id, process_start=START,
                seed=seeds[process_id - 1], scenario=scenario, duration_hours=duration_hours,
                initial_brix=rng.uniform(21, 27), ambient_c=rng.uniform(19, 25),
                fault_at_hours=rng.uniform(40, min(100, duration_hours - 12)))
            result.append((role, spec))
    return result


def build_dataset(seed=2026, per_scenario=20, duration_hours=240):
    rows, trajectories = [], []
    excluded = Counter()
    for split, spec in specs(seed, per_scenario, duration_hours):
        trajectory = Trajectory(spec)
        samples = [trajectory.sample(i) for i in range(duration_hours * 12 + 1)]
        observations = [Observation(spec.process_id, START + timedelta(minutes=5*i),
                                   START + timedelta(minutes=5*i), s["brix_apparent"],
                                   s["temperature_c"], calibration_id=spec.process_id)
                        for i, s in enumerate(samples)]
        event = first_event([s["latent_brix"] for s in samples[::12]], spec.asymptote_brix)
        trajectories.append({"split": split, "spec": spec.model_dump(mode="json"), "event": event})
        for hour in range(24, duration_hours + 1, STRIDE_HOURS):
            cutoff = START + timedelta(hours=hour)
            # Bounded past slice for performance; extract still enforces both clocks.
            features = extract(observations[(hour-24)*12:hour*12+1],
                               process_id=spec.process_id, process_start=START, as_of=cutoff)
            label, reason = risk_label(hour, event, duration_hours)
            if reason:
                excluded[reason] += 1
            target = samples[(hour+24)*12]["brix_apparent"] if hour + 24 <= duration_hours else None
            if not features["eligible"]:
                excluded["feature_abstention"] += 1
            rows.append({"process_id": spec.process_id, "seed": spec.seed,
                         "scenario": spec.scenario, "source": "simulado", "split": split,
                         "hour": hour, "as_of": cutoff.isoformat(),
                         "eligible": features["eligible"], "risk_target": label,
                         "risk_exclusion": reason, "forecast_target": target,
                         "event_onset_hour": event["onset_hour"] if event else None,
                         **features["features"]})
    return rows, {"target_version": TARGET_VERSION, "simulator_version": MODEL_VERSION,
                  "generation_seed": seed, "per_scenario": per_scenario,
                  "duration_hours": duration_hours, "stride_hours": STRIDE_HOURS,
                  "horizon_hours": HORIZON_HOURS, "minimum_lead_hours": MIN_LEAD_HOURS,
                  "persistence_hours": PERSISTENCE_HOURS, "forecast_hours": FORECAST_HOURS,
                  "feature_names": list(FEATURES), "trajectories": trajectories,
                  "excluded_risk_windows": dict(excluded)}


def validate_partition(rows):
    """Reject trajectory/seed overlap, missing roles, nonfinite model inputs."""
    import math
    roles = {"train", "calibration", "validation", "test"}
    if {r["split"] for r in rows} != roles:
        raise ValueError("Expected train/calibration/validation/test")
    processes, seeds, windows = {}, {}, set()
    for row in rows:
        window = (row["process_id"], row["hour"])
        if window in windows:
            raise ValueError("Duplicate process window")
        windows.add(window)
        identity = (row["split"], row["seed"])
        if processes.setdefault(row["process_id"], identity) != identity:
            raise ValueError("Process crosses partitions or seeds")
        identity = (row["split"], row["process_id"])
        if seeds.setdefault(row["seed"], identity) != identity:
            raise ValueError("Seed reused across processes or partitions")
        if row["eligible"] and any(row[f] is None or not math.isfinite(row[f]) for f in FEATURES):
            raise ValueError("Nonfinite eligible features")
