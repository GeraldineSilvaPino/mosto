"""Current monitoring diagnostics and explicit silence sweep; GET never writes."""
from datetime import timedelta

from app import models as m
from app.services.telemetry_v2 import aware
from app.services.episodes import record_action

SILENCE_SECONDS = 900
VERSION = "silence-v1"


def monitoring_status(db, process, now):
    now = aware(now)
    received = db.query(m.MensajeTelemetria).filter(
        m.MensajeTelemetria.fermentacion_id == process.id,
        m.MensajeTelemetria.recibido_en <= now,
    ).order_by(m.MensajeTelemetria.recibido_en.desc(), m.MensajeTelemetria.id.desc()).first()
    from app.services.simulation_time import message_clock, process_clock_at
    clock = message_clock(db, received) if received else process_clock_at(db, process.id, now)
    observation_cutoff = clock.simulated_at(now) if clock else now
    observed = db.query(m.MensajeTelemetria).filter(
        m.MensajeTelemetria.fermentacion_id == process.id,
        m.MensajeTelemetria.recibido_en <= now,
        m.MensajeTelemetria.observado_en <= observation_cutoff,
    ).order_by(m.MensajeTelemetria.observado_en.desc()).first()
    receipt_age = (now - aware(received.recibido_en)).total_seconds() if received else None
    observation_age = ((observation_cutoff - aware(observed.observado_en)).total_seconds()
                       if observed else None)
    delivery_age = ((now - (clock.real_at(aware(observed.observado_en)) if clock else aware(observed.observado_en))).total_seconds()
                    if observed else None)
    if process.fecha_real_fin is not None:
        status = "proceso_cerrado"
    elif received is None:
        status = "sin_telemetria_v2"
    elif receipt_age > SILENCE_SECONDS:
        status = "sin_recepcion_reciente"
    elif delivery_age is None or delivery_age > SILENCE_SECONDS:
        status = "mediciones_atrasadas"
    else:
        status = "datos_recientes"
    states = {s.codigo: s for s in db.query(m.EstadoRegla).filter_by(fermentacion_id=process.id)}
    profile = process.perfil if process.perfil_id and process.perfil_snapshot is None else None
    from app.services.profile_overrides import applied_profile
    applied = applied_profile(db, process, profile, now)
    thermal = {}
    for code in ("temperatura_alta", "temperatura_baja"):
        if code in states:
            thermal[code] = "configuracion_congelada"
        elif applied.get("temp_min") is None or applied.get("temp_max") is None:
            thermal[code] = "sin_limites_de_perfil"
        else:
            thermal[code] = "pendiente_primera_evaluacion"
    return {"version": VERSION, "evaluated_at": now.isoformat(), "status": status,
            "silence_threshold_seconds": SILENCE_SECONDS,
            "last_received_at": aware(received.recibido_en).isoformat() if received else None,
            "last_observed_at": aware(observed.observado_en).isoformat() if observed else None,
            "receipt_age_seconds": receipt_age, "observation_age_seconds": observation_age,
            "observation_clock": "simulated" if clock else "real",
            "expected_delivery_age_seconds": delivery_age,
            "simulation_clock": clock.model_dump(mode="json") if clock else None,
            "thermal_rules": thermal,
            "current_profile_override_revision": applied.get('override_revision', 0),
            "thermal_episode_policy": "Los episodios abiertos conservan sus umbrales de confirmación y recuperación",
            "kinetic_rule": "experimental_simulado" if "brix_ralentizacion" in states else "sin_configurar",
            "interpretation": "Frescura y configuración; datos recientes no acreditan calidad ni fermentación sana"}


def sweep_silence(db, now):
    """Caller commits. Tank -> state -> episode locks match ingestion/closure.

    No first-time incidents: marks existing conditions unknown and resets pending
    persistence. Never advances the observation watermark or claims recovery.
    """
    now = aware(now)
    changed = 0
    ids = db.query(m.ProcesoFermentacion.id, m.ProcesoFermentacion.cuba_id).filter(
        m.ProcesoFermentacion.fecha_real_fin.is_(None)).order_by(m.ProcesoFermentacion.cuba_id).all()
    for process_id, cube_id in ids:
        db.query(m.Cuba).filter_by(id=cube_id).with_for_update().one()
        process = db.query(m.ProcesoFermentacion).filter_by(id=process_id).populate_existing().one()
        if process.fecha_real_fin is not None:
            continue
        status = monitoring_status(db, process, now)
        if status["status"] not in {"sin_recepcion_reciente", "mediciones_atrasadas"}:
            continue
        for state in db.query(m.EstadoRegla).filter_by(fermentacion_id=process_id).with_for_update():
            clock_data = status.get("simulation_clock")
            from app.simulation.clock import SimulationClock
            expected_real = (SimulationClock.model_validate(clock_data).real_at(aware(state.ultima_observacion))
                             if clock_data else aware(state.ultima_observacion))
            if expected_real >= now - timedelta(seconds=SILENCE_SECONDS):
                continue
            state.inicio_candidato = state.inicio_recuperacion = None
            if not state.episodio_id:
                continue
            episode = db.query(m.EventoAlerta).filter_by(id=state.episodio_id).with_for_update().one()
            if episode.fin_condicion is not None or episode.estado_condicion == "desconocida":
                continue
            episode.estado_condicion = "desconocida"
            record_action(db, episode, "silencio_detectado", registered=now,
                          detail=status)  # No observed timestamp: this is a server check.
            changed += 1
    return changed
