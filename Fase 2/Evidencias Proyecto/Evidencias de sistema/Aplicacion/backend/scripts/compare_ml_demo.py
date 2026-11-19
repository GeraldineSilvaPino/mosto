"""Reproduce the illustrative values displayed by CubaDetailView; no DB writes.

Run from backend: python -m scripts.compare_ml_demo
These examples demonstrate behavior, not held-out performance or real-world calibration.
"""
import json
from datetime import datetime, timedelta, timezone
import numpy as np
from app.simulation.model import SimulationSpec, Trajectory
from app.services.kinetics import Observation, extract, FEATURES
from app.services.ml_service import get_calibrated_model


def main():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bundle = get_calibrated_model()
    results = []
    for scenario in ('healthy', 'cold_shock', 'heat_stress'):
        trajectory = Trajectory(SimulationSpec(process_id=1, process_start=start,
                                              seed=20261119, scenario=scenario))
        rows = []
        for index in range(42 * 12, 66 * 12 + 1):
            sample = trajectory.sample(index)
            at = start + timedelta(minutes=index * 5)
            rows.append(Observation(1, at, at, sample['brix_apparent'],
                                    sample['temperature_c'], calibration_id=1))
        result = extract(rows, process_id=1, process_start=start, as_of=start + timedelta(hours=66))
        assert result['eligible']
        x = np.array([[result['features'][name] for name in FEATURES]])
        score = bundle['classifier'].decision_function(x).reshape(-1, 1)
        risk = float(bundle['calibrator'].predict_proba(score)[0, 1]) * 100
        results.append(dict(scenario=scenario, age_hours=66, seed=20261119, risk_pct=risk))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
