"""Descriptive series shared by the detail and process history screens.

Legacy readings have no receipt timestamp. Keep that limitation explicit and
never pass them off as calibrated v2 observations or predictive features.
"""
from collections import Counter
from datetime import timedelta
import math

import numpy as np

from app import models as m
from app.services.telemetry_v2 import aware


def legacy_series(db, process, left, right, variable, limit=10000):
    field = {'temperatura': 'temp_mosto', 'brix_aparente': 'brix',
             'ph': 'ph', 'densidad': 'densidad_sg'}[variable]
    query = db.query(m.LecturaTelemetria).outerjoin(
        m.MensajeTelemetria, m.MensajeTelemetria.lectura_id == m.LecturaTelemetria.id).filter(
        m.LecturaTelemetria.fermentacion_id == process.id,
        m.MensajeTelemetria.id.is_(None),
        m.LecturaTelemetria.timestamp >= max(left, aware(process.fecha_inicio)),
        m.LecturaTelemetria.timestamp <= right)
    count = query.count()
    rows = query.order_by(m.LecturaTelemetria.timestamp, m.LecturaTelemetria.id).limit(limit).all()
    duplicates = Counter(aware(r.timestamp) for r in rows)
    points = []
    for row in rows:
        value = getattr(row, field)
        valid = (row.lectura_valida and value is not None and math.isfinite(float(value))
                 and duplicates[aware(row.timestamp)] == 1
                 and not (count > limit and row.timestamp == rows[-1].timestamp))
        points.append(dict(id=row.id, observed_at=aware(row.timestamp), available_at=None,
            value=float(value) if valid else None, source=row.origen_dato or 'legacy',
            device_id=row.dispositivo_id, calibration_id=None))
    return points, count


def descriptive_metrics(db, process, end, cutoff):
    """Display each adequately covered window without requiring a full 24 h.

    These metrics do not change predictive eligibility or incident rules.
    """
    left = max(aware(process.fecha_inicio), end - timedelta(hours=24))
    v2 = db.query(m.MensajeTelemetria).filter(
        m.MensajeTelemetria.fermentacion_id == process.id,
        m.MensajeTelemetria.recibido_en <= cutoff)
    has_v2 = v2.first() is not None
    rows = v2.filter(m.MensajeTelemetria.observado_en >= left,
                     m.MensajeTelemetria.observado_en <= end).order_by(m.MensajeTelemetria.observado_en).all()
    duplicates = Counter(aware(r.observado_en) for r in rows)
    metrics, sources = {}, set()
    latest = None
    for channel, variable, field, quality in (
        ('brix', 'brix_aparente', 'brix', 'calidad_brix'),
        ('temperature', 'temperatura', 'temperatura', 'calidad_temperatura')):
        if has_v2:
            points = [dict(observed_at=aware(r.observado_en), value=getattr(r, field)
                if getattr(r, quality) == 'good' and duplicates[aware(r.observado_en)] == 1
                and (channel != 'brix' or r.calibracion_id is not None) else None,
                source=r.origen, device_id=r.dispositivo_id, calibration_id=r.calibracion_id) for r in rows]
        else:
            points, total = legacy_series(db, process, left, end, variable)
            if total > len(points):
                continue  # Do not summarize a truncated high-frequency history.
        sources.update(p['source'] for p in points)
        valid = [p for p in points if p['value'] is not None and math.isfinite(p['value'])]
        if valid:
            stamp = valid[-1]['observed_at']
            latest = max(latest, stamp) if latest else stamp
            metrics[f'{channel}_latest'] = valid[-1]['value']
        for hours in (1, 6, 24):
            start = end - timedelta(hours=hours)
            window = [p for p in points if p['observed_at'] >= start]
            if len(window) < 2 or any(p['value'] is None for p in window):
                continue
            if len({(p['source'], p['device_id'], p['calibration_id']) for p in window}) != 1:
                continue
            times = [p['observed_at'] for p in window]
            gaps = [(b - a).total_seconds() for a, b in zip([start] + times, times + [end])]
            if max(gaps) > 900 or (times[-1] - times[0]).total_seconds() < hours * 3600 * .8:
                continue
            values = [float(p['value']) for p in window]
            if hours == 1:
                metrics[f'{channel}_mean_1h'] = float(np.mean(values))
            if channel == 'brix' and hours in (6, 24):
                x = [(t - times[0]).total_seconds() / 3600 for t in times]
                metrics[f'brix_slope_{hours}h'] = float(np.polyfit(x, values, 1)[0])
    return dict(metrics=metrics, sources=sorted(sources), latest_at=latest,
                legacy=not has_v2, observation_as_of=end)
