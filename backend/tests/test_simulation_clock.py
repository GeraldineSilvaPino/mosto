"""Time domains, transport delays and serialized restart of the clock primitive."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.simulation.clock import SimulationClock


def clock(factor=60):
    return SimulationClock(real_anchor="2026-11-18T12:00:00Z",
                           simulated_anchor="2026-11-01T00:00:00Z", factor=factor)


def test_accelerated_biology_and_real_transport_delay():
    c = clock()
    observed = c.simulated_anchor + timedelta(hours=1)
    assert c.simulated_at(c.real_anchor + timedelta(minutes=1)) == observed
    assert c.delivery_at(observed, 120) == c.real_anchor + timedelta(minutes=3)
    assert c.simulated_at(c.real_anchor - timedelta(seconds=1)) == c.simulated_anchor - timedelta(minutes=1)


@pytest.mark.parametrize("factor", [1, 60, 180, 3600])
def test_roundtrip_and_restart_preserve_clock(factor):
    c = clock(factor)
    restored = SimulationClock.model_validate_json(c.model_dump_json())
    instant = c.real_anchor + timedelta(seconds=12345, microseconds=123456)
    assert restored.real_at(restored.simulated_at(instant)) == instant


def test_timezone_normalization_and_naive_rejection():
    c = clock()
    assert c.simulated_at(c.real_anchor.astimezone(timezone(timedelta(hours=-3)))) == c.simulated_anchor
    with pytest.raises(ValueError):
        c.simulated_at(datetime(2026, 11, 18))
    with pytest.raises(ValueError):
        c.real_at(datetime(2026, 11, 18))


@pytest.mark.parametrize("factor", [0, -1, .5, 3601, float("inf"), float("nan")])
def test_invalid_factors_rejected(factor):
    with pytest.raises(ValidationError):
        clock(factor)


@pytest.mark.parametrize("delay", [-1, float("inf"), float("nan")])
def test_invalid_transport_delay_rejected(delay):
    c = clock()
    with pytest.raises(ValueError):
        c.delivery_at(c.simulated_anchor, delay)
