from datetime import datetime, timedelta, timezone
import json

import pytest

from app.simulation.worker import EmitterConfig, FleetConfig, Worker, run_id, canonical_json
from uuid import uuid5, NAMESPACE_URL


REAL = datetime(2026, 11, 18, tzinfo=timezone.utc)
SIM = REAL + timedelta(days=10)


def config(faults=None):
    return EmitterConfig(device_id=1, calibration_id=1, key_env='MOSTO_SIM_DEVICE_1',
        simulation=dict(process_id=1, process_start=SIM, seed=42, scenario='healthy'),
        simulation_clock=dict(real_anchor=REAL, simulated_anchor=SIM, factor=60),
        emitter_faults=faults)


class Sender:
    def __init__(self):
        self.sent = []; self.now = REAL; self.fail = False; self.mismatch = False

    def verify(self, c, token):
        data = c.model_dump(mode='json')
        return 200, dict(source='simulado', device_id=1, calibration_id=1,
            simulation=data['simulation'], emitter_faults=data['emitter_faults'],
            simulation_clock=None if self.mismatch else data['simulation_clock'])

    def __call__(self, body, token):
        self.sent.append(body)
        if self.fail:
            self.fail = False
            return 503, {}
        return 201, dict(message_id=body['sequence']+1, duplicate=False, device_id=1,
            process_id=1, source='simulado', observed_at=body['observed_at'], received_at=self.now,
            temperature_c=body['temperature_c'], brix_apparent=body['brix_apparent'],
            out_of_order=False, delayed=False, diagnostics=[])


def worker(c, path, sender):
    return Worker(FleetConfig(base_url='http://127.0.0.1:8000', devices=[c]), path,
                  sender=sender, keys={'MOSTO_SIM_DEVICE_1':'test-key'})


def test_restart_retries_exact_envelope_and_uses_real_backoff(tmp_path):
    c, sender = config(), Sender()
    sender.fail = True
    path = tmp_path / 'state.db'
    w = worker(c, path, sender)
    assert w.tick(REAL) == 0
    first = sender.sent[0]
    assert w.tick(REAL + timedelta(seconds=1)) == 0
    w.close()
    w = worker(c, path, sender)
    try:
        sender.now = REAL + timedelta(seconds=5)
        assert w.tick(sender.now) == 2
        assert sender.sent[1] == first
        assert sender.sent[2]['observed_at'] == (SIM+timedelta(minutes=5)).isoformat()
        assert w.statuses()[0]['pending'] == 0
    finally:
        w.close()
    changed=c.model_dump(mode='json'); changed['simulation_clock']['factor']=180
    with pytest.raises(ValueError, match='recipe changed'):
        worker(EmitterConfig.model_validate(changed), path, sender)


@pytest.mark.parametrize('kind,release', [('delivery_delay',120), ('communication_outage',10)])
def test_fault_delivery_uses_correct_clock(tmp_path, kind, release):
    event=dict(kind=kind,start_sequence=0,end_sequence=2)
    if kind=='delivery_delay': event['delay_seconds']=120
    c=config(dict(events=[event])); sender=Sender(); w=worker(c,tmp_path/'fault.db',sender)
    try:
        assert w.tick(REAL)==0
        assert w.tick(REAL+timedelta(seconds=release-1))==0
        sender.now=REAL+timedelta(seconds=release)
        assert w.tick(sender.now)>=1
        assert sender.sent[0]['observed_at']==SIM.isoformat()
    finally:
        w.close()


def test_mismatch_blocks_before_generation_and_legacy_identity_stable(tmp_path):
    c=config(); sender=Sender(); sender.mismatch=True
    w=worker(c,tmp_path/'mismatch.db',sender)
    try:
        assert w.tick(REAL)==0
        assert w.statuses()[0]['last_error']=='preflight_recipe_mismatch'
        assert w.statuses()[0]['generated_sequence']==0
    finally:
        w.close()
    legacy=c.model_copy(update={'simulation_clock':None})
    data=legacy.model_dump(mode='json',exclude={'key_env','simulation_clock','emitter_faults'})
    assert run_id(legacy)==str(uuid5(NAMESPACE_URL,'mosto/simulation/'+canonical_json(data)))
