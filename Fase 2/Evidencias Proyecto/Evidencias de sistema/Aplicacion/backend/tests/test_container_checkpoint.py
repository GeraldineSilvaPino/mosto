"""Checkpoint recovery tests with an isolated SQLite database, no remote access."""
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

os.environ['MOSTO_ENV'] = 'test'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'checkpoint-test-key-with-at-least-32-bytes'

from sqlalchemy import create_engine, text
from app.simulation.model import SimulationSpec
from app.simulation.worker import EmitterConfig, FleetConfig, Worker, run_id
from scripts.simulate_container import restore_checkpoint


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = EmitterConfig(device_id=12, calibration_id=1, key_env='MOSTO_SIM_DEVICE_12',
            simulation=SimulationSpec(process_id=13, process_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                                      seed=42, scenario='healthy'))
        self.worker = Worker(FleetConfig(base_url='http://127.0.0.1:8000', devices=[self.config]),
                             Path(self.directory.name)/'state.sqlite')
        self.engine = create_engine('sqlite:///:memory:')
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE "MENSAJE_TELEMETRIA" (dispositivo_id int, boot_id text, secuencia int)'))

    def tearDown(self):
        self.worker.close()
        self.engine.dispose()
        self.directory.cleanup()

    def recover(self, sequences, boot=None):
        with self.engine.begin() as c:
            for sequence in sequences:
                c.execute(text('INSERT INTO "MENSAJE_TELEMETRIA" VALUES (12,:boot,:seq)'),
                          {'boot': (boot or run_id(self.config)).replace('-', ''), 'seq': sequence})
            return restore_checkpoint(self.worker, self.config, c)

    def test_fresh_ephemeral_state_recovers_acknowledged_prefix(self):
        self.assertEqual(self.recover([0, 1, 2, 3]), 4)
        state = self.worker.statuses()[0]
        self.assertEqual((state['next_sequence'], state['generated_sequence']), (4, 4))

    def test_gap_is_replayed_instead_of_skipping_missing_reading(self):
        self.assertEqual(self.recover([0, 1, 3]), 2)
        self.assertEqual(self.worker.statuses()[0]['next_sequence'], 2)

    def test_other_trajectory_does_not_advance_checkpoint(self):
        self.assertEqual(self.recover([0, 1], 'other-trajectory'), 0)


if __name__ == '__main__':
    unittest.main()
