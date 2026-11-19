"""Exercise actual temporal features and shipped model, without a database."""
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from app.services.kinetics import Observation, extract
from app.services.ml_service import evaluar_proceso_cinetica
from app.simulation.model import SimulationSpec, Trajectory


class TemporalReadinessTests(unittest.TestCase):
    def evaluate(self, hours, stale=False):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(hours=hours)
        model = Trajectory(SimulationSpec(process_id=13, process_start=start, seed=42, scenario='healthy'))
        rows = []
        for index in range(hours * 12 + 1 - (4 if stale else 0)):
            at = start + timedelta(minutes=index * 5)
            sample = model.sample(index)
            rows.append(Observation(13, at, at, sample['brix_apparent'], sample['temperature_c'], calibration_id=1))
        result = extract(rows, process_id=13, process_start=start, as_of=end)
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = SimpleNamespace(id=13)
        with patch('app.services.kinetics_query.process_kinetics', return_value=result), \
             patch('app.services.simulation_time.process_clock_at', return_value=None), \
             patch('app.services.simulation_time.observation_end', return_value=end):
            return evaluar_proceso_cinetica(db, 13)

    def test_seven_hours_explains_wait_without_fabricating_probability(self):
        result = self.evaluate(7)
        self.assertIsNone(result['riesgo_pct'])
        self.assertIn('24 h', result['mensaje'])
        self.assertIn('7.0 h', result['mensaje'])
        self.assertIn('cobertura', result['mensaje'])

    def test_full_window_runs_shipped_model(self):
        result = self.evaluate(25)
        self.assertIsInstance(result['riesgo_pct'], float)
        self.assertGreaterEqual(result['riesgo_pct'], 0)
        self.assertLessEqual(result['riesgo_pct'], 100)
        self.assertIn(result['estado_ia'], ['NORMAL', 'ADVERTENCIA', 'CRITICO'])

    def test_old_latest_sample_does_not_report_risk(self):
        result = self.evaluate(25, stale=True)
        self.assertIsNone(result['riesgo_pct'])
        self.assertIn('15 min', result['mensaje'])


if __name__ == '__main__':
    unittest.main()
