"""Read-only, availability-aware curves. No fitting, interpolation or causal claims."""
from collections import Counter
from datetime import timedelta
import math

from sqlalchemy import and_
from app import models as m
from app.services.telemetry_v2 import aware

VERSION = 'curve-comparison-v1'
TELEMETRY_LIMIT = 3000
MANUAL_LIMIT = 300
MAX_GAP_SECONDS = 900
VARIABLES = {
    'temperatura': ('°C', 'temperatura', 'calidad_temperatura'),
    'brix_aparente': ('°Bx', 'brix', 'calidad_brix'),
    'densidad': ('g/mL', None, None),
    'ph': ('pH', None, None),
}


def curves(db, process, variable, age_start, age_end, cutoff):
    start = aware(process.fecha_inicio)
    left, right = start + timedelta(hours=age_start), min(start + timedelta(hours=age_end), cutoff)
    if process.fecha_real_fin:
        right = min(right, aware(process.fecha_real_fin))
    unit, value_field, quality_field = VARIABLES[variable]
    query = db.query(m.MensajeTelemetria).filter(
        m.MensajeTelemetria.fermentacion_id == process.id,
        m.MensajeTelemetria.observado_en >= left, m.MensajeTelemetria.observado_en <= right,
        m.MensajeTelemetria.recibido_en <= cutoff)
    count = query.count() if value_field else 0
    rows = query.order_by(m.MensajeTelemetria.observado_en, m.MensajeTelemetria.id).limit(TELEMETRY_LIMIT).all() if value_field else []
    truncated = count > TELEMETRY_LIMIT
    # A partial series cannot establish whether the boundary timestamp is unique.
    duplicates = Counter(aware(row.observado_en) for row in rows)
    segments, segment, previous, excluded = [], None, None, 0
    for row in rows:
        observed = aware(row.observado_en)
        value = getattr(row, value_field)
        identity = (row.origen, row.dispositivo_id, row.calibracion_id)
        invalid = (getattr(row, quality_field) != 'good' or value is None or not math.isfinite(value)
                   or (variable == 'brix_aparente' and row.calibracion_id is None)
                   or duplicates[observed] > 1 or (truncated and observed == aware(rows[-1].observado_en)))
        if invalid:
            segment, previous = None, None
            excluded += 1
            continue
        if previous is None or identity != previous[0] or (observed - previous[1]).total_seconds() > MAX_GAP_SECONDS:
            segment = dict(source=row.origen, device_id=row.dispositivo_id, calibration_id=row.calibracion_id, points=[])
            segments.append(segment)
        segment['points'].append(dict(id=row.id, hour=(observed - start).total_seconds() / 3600,
            value=value, observed_at=observed, available_at=aware(row.recibido_en)))
        previous = identity, observed

    manual_query = db.query(m.MedicionManual, m.AnulacionMedicion).outerjoin(m.AnulacionMedicion, and_(
        m.AnulacionMedicion.medicion_id == m.MedicionManual.id,
        m.AnulacionMedicion.registrado_en <= cutoff)).filter(
        m.MedicionManual.fermentacion_id == process.id, m.MedicionManual.variable == variable,
        m.MedicionManual.observado_en >= left, m.MedicionManual.observado_en <= right,
        m.MedicionManual.registrado_en <= cutoff)
    manual_count = manual_query.count()
    manual_rows = manual_query.order_by(m.MedicionManual.observado_en, m.MedicionManual.id).limit(MANUAL_LIMIT).all()
    manual = []
    for row, annulment in manual_rows:
        manual.append(dict(id=row.id, source='manual', method=row.metodo, instrument=row.instrumento,
            unit=row.unidad, value=row.valor, hour=(aware(row.observado_en) - start).total_seconds() / 3600,
            observed_at=aware(row.observado_en), available_at=aware(row.registrado_en), author_id=row.usuario_id,
            evidence=row.evidencia, alert_id=row.alerta_id, intervention_id=row.intervencion_id,
            annulment=None if annulment is None else dict(reason=annulment.motivo,
                available_at=aware(annulment.registrado_en), author_id=annulment.usuario_id)))
    warnings = []
    if not value_field:
        warnings.append('sin_canal_automatico')
    elif not rows:
        warnings.append('sin_telemetria_disponible')
    if excluded:
        warnings.append('muestras_no_graficables')
    if not manual:
        warnings.append('sin_contrastes_manuales')
    if truncated or manual_count > MANUAL_LIMIT:
        warnings.append('limite_de_registros')
    if any(row['annulment'] for row in manual):
        warnings.append('mediciones_anuladas')
    if variable == 'brix_aparente' and manual:
        warnings.append('metodos_brix_no_equivalentes')
    sources = sorted({row.origen for row in rows})
    if 'simulado' in sources:
        warnings.append('incluye_simulacion')
    if len(sources) > 1:
        warnings.append('origenes_mixtos')
    cube = db.query(m.Cuba).filter_by(id=process.cuba_id).one()
    return dict(process_id=process.id, tank=cube.codigo, process_start=start,
        window_start=left, window_end=right if right >= left else None,
        sources=sources, segments=segments, manual=manual, warnings=warnings,
        telemetry=dict(total=count, returned=len(rows), excluded=excluded, truncated=truncated),
        manual_counts=dict(total=manual_count, returned=len(manual), truncated=manual_count > MANUAL_LIMIT),
        # Lifecycle metadata is current, explicitly outside the historical observation snapshot.
        current_state=process.estado, unit=unit)
