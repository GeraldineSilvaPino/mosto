from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.services.kinetics import Observation, extract
from test_telemetry_v2 import packet, send  # reusable canonical ingestion fixture

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(hours=24)


def series(minutes=5):
    return [Observation(1, START + timedelta(minutes=m), START + timedelta(minutes=m),
                        24 - .1 * m / 60, 20 + .02 * m / 60, calibration_id=1)
            for m in range(0, 1441, minutes)]


def evaluate(rows, as_of=END):
    return extract(rows, process_id=1, process_start=START, as_of=as_of)


def test_rates_use_hours_and_are_stable_across_sampling_cadence():
    five, ten = evaluate(series()), evaluate(series(10))
    assert five["eligible"] and ten["eligible"]
    for key in ("brix_slope_6h", "brix_slope_24h", "brix_rate_smoothed"):
        assert five["features"][key] == pytest.approx(-.1, abs=.0001)
        assert ten["features"][key] == pytest.approx(-.1, abs=.0002)
    assert five["features"]["temperature_slope_6h"] == pytest.approx(.02)


def test_future_late_arrivals_and_other_process_cannot_change_past():
    rows = series()
    poison = [replace(rows[-1], observed_at=END + timedelta(seconds=1), brix=999),
              replace(rows[20], received_at=END + timedelta(seconds=1), brix=999),
              replace(rows[20], process_id=2, brix=999)]
    assert evaluate(rows) == evaluate(list(reversed(rows + poison)))


@pytest.mark.parametrize("mutate,reason", [
    (lambda rows: rows[:-5], "brix_stale"),
    (lambda rows: rows[:100] + rows[120:], "brix_gap"),
    (lambda rows: [replace(r, calibration_id=None) for r in rows], "brix_coverage"),
    (lambda rows: rows[:150] + [replace(r, calibration_id=2) for r in rows[150:]],
     "brix_calibration_or_device_change"),
    (lambda rows: rows + [rows[-1]], "ambiguous_timestamps"),
    (lambda rows: [replace(r, brix=float("nan")) for r in rows], "brix_coverage"),
])
def test_abstention(mutate, reason):
    result = evaluate(mutate(series()))
    assert not result["eligible"] and reason in result["abstention_reasons"]
    assert result["features"]["brix_slope_6h"] is None


def test_temperature_failure_does_not_erase_brix():
    result = evaluate([replace(r, temperature=None, temperature_quality="missing") for r in series()])
    assert not result["eligible"]
    assert result["features"]["brix_slope_6h"] == pytest.approx(-.1)
    assert result["features"]["temperature_mean_1h"] is None


def test_current_bad_quality_is_not_hidden_by_recent_good_reading():
    rows = series()
    rows[-1] = replace(rows[-1], brix_quality="invalid")
    result = evaluate(rows)
    assert not result["eligible"]
    assert "brix_latest_quality" in result["abstention_reasons"]
    assert result["features"]["brix_slope_6h"] is None
    assert result["features"]["temperature_mean_1h"] is not None


def test_recent_hole_is_not_hidden_by_total_coverage():
    rows = series()
    result = evaluate(rows[:-12] + rows[-1:])
    assert result["channels"]["brix"]["coverage"] > .8
    assert "brix_recent_coverage" in result["abstention_reasons"]


def test_slowdown_is_descriptive_and_lag_is_not_a_stop():
    rows = series()
    plateau = [replace(r, brix=max(r.brix, 22.4)) for r in rows]
    assert evaluate(plateau)["observation"] == "ralentizacion_observada"
    assert evaluate([replace(r, brix=24) for r in rows])["observation"] == "sin_desviacion_detectada"
    assert not evaluate(rows[:12], START + timedelta(hours=1))["eligible"]


def test_timezone_required():
    with pytest.raises(ValueError, match="Timezone"):
        evaluate(series(), END.replace(tzinfo=None))


def test_api_is_scoped_and_keeps_unknown_risk(client):
    response = client.get("/api/procesos/1/cinetica")
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body["eligible"] and body["riesgo_pct"] is None
    assert body["estado_ia"] == "NO_VALIDADO" and not body["alerta_ia"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/procesos/999999/cinetica").status_code == 404
    assert client.get("/api/procesos/1/cinetica", params={"as_of": "2099-01-01T00:00:00Z"}).status_code == 422
    assert client.get("/api/procesos/1/cinetica", params={"as_of": "2026-01-01"}).status_code == 422
    client.headers.pop("Authorization")
    assert client.get("/api/procesos/1/cinetica").status_code == 401


def test_api_historical_cutoff_excludes_delayed_receipt(client, packet):
    response = send(client, packet)
    assert response.status_code == 201, response.text
    receipt = datetime.fromisoformat(response.json()["received_at"].replace("Z", "+00:00"))
    before = client.get("/api/procesos/1/cinetica", params={
        "as_of": (receipt - timedelta(seconds=1)).isoformat()}).json()
    after = client.get("/api/procesos/1/cinetica").json()
    assert before["channels"]["brix"]["usable_samples"] == 0
    assert after["channels"]["brix"]["usable_samples"] == 1
    assert after["riesgo_pct"] is None and not after["eligible"]
