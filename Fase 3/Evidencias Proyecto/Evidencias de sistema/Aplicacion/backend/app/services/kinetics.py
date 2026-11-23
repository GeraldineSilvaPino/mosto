"""Shared causal feature extraction. Pure: no DB, model, wall clock or network."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

import numpy as np

VERSION = "kinetics-v1"
WINDOW_HOURS = 24
GRID_SECONDS = 300
MAX_HOLD_SECONDS = 900
FEATURES = (
    "age_hours", "brix_mean_1h", "brix_rate_smoothed", "brix_slope_6h",
    "brix_slope_24h", "brix_residual_std", "temperature_mean_1h",
    "temperature_mean_24h", "temperature_range_24h", "temperature_slope_6h",
)


def utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Observation:
    process_id: int
    observed_at: datetime
    received_at: datetime
    brix: float | None
    temperature: float | None
    brix_quality: str = "good"
    temperature_quality: str = "good"
    calibration_id: str | int | None = None
    device_id: int = 1
    source: str = "simulado"


def _channel(rows, grid, channel):
    def valid(r):
        return (getattr(r, channel + "_quality") == "good"
                and getattr(r, channel) is not None and math.isfinite(getattr(r, channel))
                and (channel != "brix" or r.calibration_id is not None))

    usable = [r for r in rows if valid(r)]
    times = np.array([utc(r.observed_at).timestamp() for r in usable])
    values = np.full(len(grid), np.nan)
    if rows:
        # An explicit invalid/missing measurement is a barrier: do not carry
        # an older good value across a sensor's reported failure.
        all_times = np.array([utc(r.observed_at).timestamp() for r in rows])
        indices = np.searchsorted(all_times, grid, side="right") - 1
        held = (indices >= 0) & (grid - all_times[np.maximum(indices, 0)] <= MAX_HOLD_SECONDS)
        raw = np.array([getattr(r, channel) if valid(r) else np.nan for r in rows])
        values[held] = raw[indices[held]]
    gaps = np.diff(np.concatenate(([grid[0]], times, [grid[-1]])))
    coverage = float(np.isfinite(values).mean())
    age = float(grid[-1] - times[-1]) if len(times) else None
    diagnostic = {"coverage": coverage, "max_gap_seconds": float(max(gaps)),
                  "latest_age_seconds": age, "usable_samples": len(usable),
                  "latest_quality_good": bool(rows and valid(rows[-1]))}
    return values, diagnostic


def _slope(x, y):
    valid = np.isfinite(y)
    coefficients = np.polyfit(x[valid], y[valid], 1)
    residual = y[valid] - np.polyval(coefficients, x[valid])
    return float(coefficients[0]), float(np.std(residual))


def extract(observations, *, process_id, process_start, as_of, received_as_of=None):
    as_of, process_start = utc(as_of), utc(process_start)
    # Observation age and real availability may use different clocks in an
    # explicitly accelerated simulation. Legacy callers retain a single cutoff.
    received_as_of = as_of if received_as_of is None else utc(received_as_of)
    if as_of < process_start:
        raise ValueError("Inference precedes process start")
    start = as_of - timedelta(hours=WINDOW_HOURS)
    rows = sorted((r for r in observations if r.process_id == process_id
                   and max(start, process_start) <= utc(r.observed_at) <= as_of
                   and utc(r.received_at) <= received_as_of), key=lambda r: utc(r.observed_at))
    grid = np.arange(289) * GRID_SECONDS + start.timestamp()
    x = (grid - grid[-1]) / 3600
    reasons = []
    duplicate = len({utc(r.observed_at) for r in rows}) != len(rows)
    if duplicate:
        reasons.append("ambiguous_timestamps")
    sources = sorted({r.source for r in rows})
    if len(sources) > 1:
        reasons.append("mixed_sources")
    brix, bq = _channel(rows, grid, "brix")
    temp, tq = _channel(rows, grid, "temperature")
    channels = {"brix": bq, "temperature": tq}
    valid_channels = {}
    for name, quality in channels.items():
        failures = []
        if quality["coverage"] < .8:
            failures.append("coverage")
        if quality["max_gap_seconds"] > 1800:
            failures.append("gap")
        if quality["latest_age_seconds"] is None or quality["latest_age_seconds"] > 900:
            failures.append("stale")
        if not quality["latest_quality_good"]:
            failures.append("latest_quality")
        if name == "brix" and len({(r.device_id, r.calibration_id) for r in rows}) > 1:
            failures.append("calibration_or_device_change")
        reasons.extend(f"{name}_{reason}" for reason in failures)
        valid_channels[name] = not failures and not duplicate and len(sources) <= 1
    features = dict.fromkeys(FEATURES)
    features["age_hours"] = (as_of - process_start).total_seconds() / 3600
    # Local windows must also have coverage; a good 24 h average cannot hide a hole now.
    for name, values in (("brix", brix), ("temperature", temp)):
        if any(np.isfinite(values[(x > low) & (x <= high)]).mean() < .8
               for low, high in ((-1, 0), (-2, -1), (-6, 0))):
            valid_channels[name] = False
            reasons.append(f"{name}_recent_coverage")
    if valid_channels["brix"]:
        recent = float(np.nanmean(brix[x > -1]))
        slope, residual = _slope(x, brix)
        features.update(brix_mean_1h=recent,
                        brix_rate_smoothed=recent - float(np.nanmean(brix[(x > -2) & (x <= -1)])),
                        brix_slope_6h=_slope(x[x >= -6], brix[x >= -6])[0],
                        brix_slope_24h=slope, brix_residual_std=residual)
    if valid_channels["temperature"]:
        features.update(temperature_mean_1h=float(np.nanmean(temp[x > -1])),
                        temperature_mean_24h=float(np.nanmean(temp)),
                        temperature_range_24h=float(np.nanmax(temp) - np.nanmin(temp)),
                        temperature_slope_6h=_slope(x[x >= -6], temp[x >= -6])[0])
    observation = "sin_evaluacion"
    if valid_channels["brix"]:
        observation = "sin_desviacion_detectada"
        if (features["age_hours"] >= 24 and features["brix_mean_1h"] > 5
                and features["brix_slope_6h"] > -.015 and features["brix_slope_24h"] < -.04):
            observation = "ralentizacion_observada"
    return {"version": VERSION, "process_id": process_id, "as_of": as_of.isoformat(),
            "received_as_of": received_as_of.isoformat(),
            "window_start": start.isoformat(), "eligible": not reasons,
            "abstention_reasons": reasons, "channels": channels, "features": features,
            "observation": observation, "evidence": {
                "configuration": {"version": VERSION, "window_hours": 24,
                                  "recent_slope_threshold": -.015, "prior_slope_threshold": -.04},
                "confirmed_at": as_of.isoformat(), "source": sources,
                "interpretation": "Descripción de Brix aparente; no predicción ni diagnóstico causal"}}
