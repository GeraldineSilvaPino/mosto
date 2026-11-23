"""Transactional v2 thermal episodes. Observed condition != human resolution."""
from datetime import timedelta
from app import models as m
from app.services.telemetry_v2 import aware, utc_now

RULE_VERSION = "thermal-v2-1"
HOLD = timedelta(minutes=10)
MAX_GAP = timedelta(minutes=15)


def record_action(db, episode, action, *, message=None, actor=None, detail=None, observed=None, registered=None):
    db.add(m.AuditoriaAlerta(alerta_id=episode.id, accion=action,
        registrado_en=registered or utc_now(), observado_en=observed,
        usuario_id=actor, mensaje_id=message.id if message else None, detalle=detail or {}))


def _condition(db, episode, status, message):
    if episode.estado_condicion != status:
        episode.estado_condicion = status
        record_action(db, episode, status, message=message, observed=aware(message.observado_en),
                      registered=aware(message.recibido_en))


def evaluate_thermal(db, process, message):
    """Called after message flush, under the ingestion tank lock; never commits.

    Late observations at/below the per-rule watermark are retained as telemetry
    but do not rewrite episodes or human actions. Replay in timestamp order when
    reconstructing a synthetic past. Closed processes are not reopened.
    """
    if process.fecha_real_fin is not None:
        return
    observed = aware(message.observado_en)
    profile = db.get(m.PerfilFermentacion, process.perfil_id) if process.perfil_id else None
    from app.services.profile_versions import effective_profile
    applied = effective_profile(process, profile)
    from app.services.profile_overrides import adjustment_at, thermal_configuration
    from app.services.simulation_time import message_clock
    clock = message_clock(db, message)
    # Overrides become effective in server time. A delayed sample keeps the
    # configuration applicable when it was due, not when its backlog arrived.
    effective_at = clock.real_at(observed) if clock else observed
    adjustment = adjustment_at(db, process.id, effective_at)
    for code in ("temperatura_alta", "temperatura_baja"):
        state = db.query(m.EstadoRegla).filter_by(fermentacion_id=process.id, codigo=code).with_for_update().first()
        previous = aware(state.ultima_observacion) if state else None
        if previous is not None and observed <= previous:
            continue
        if state is None:
            if applied.get("temp_min") is None or applied.get("temp_max") is None:
                continue  # No guessed fallback thresholds.
            low, high = float(applied["temp_min"]), float(applied["temp_max"])
            state = m.EstadoRegla(fermentacion_id=process.id, codigo=code, ultima_observacion=observed,
                configuracion={"version": RULE_VERSION, "profile_id": process.perfil_id,
                               "profile_revision": applied.get("revision") if process.perfil_snapshot else None, "temp_min": low,
                               "temp_max": high, "hysteresis_c": min(.5, max(0, (high-low)/4)),
                               "hold_seconds": 600, "max_gap_seconds": 900})
            db.add(state)
        episode = db.query(m.EventoAlerta).filter_by(id=state.episodio_id).with_for_update().first() if state.episodio_id else None
        revision = adjustment.revision if adjustment else 0
        if episode:
            # An override never relaxes the recovery threshold of an open episode.
            config = (episode.evidencia or {}).get('configuration', state.configuracion)
        else:
            config = thermal_configuration(state.configuracion, adjustment)
            if (state.perfil_ajuste_revision or 0) != revision:
                state.inicio_candidato = state.inicio_recuperacion = None
                state.perfil_ajuste_revision = revision
        gap = previous is not None and observed - previous > MAX_GAP
        if gap:
            state.inicio_candidato = state.inicio_recuperacion = None
        state.ultima_observacion = observed
        usable = message.calidad_temperatura == "good" and message.temperatura is not None
        if not usable:
            state.inicio_candidato = state.inicio_recuperacion = None
            if episode:
                episode.ultima_observacion = observed
                _condition(db, episode, "desconocida", message)
            continue
        value = message.temperatura
        high = code == "temperatura_alta"
        limit = config["temp_max"] if high else config["temp_min"]
        outside = value > limit if high else value < limit
        recovered = value <= limit - config["hysteresis_c"] if high else value >= limit + config["hysteresis_c"]
        if episode:
            episode.ultima_observacion = observed
            if gap:
                _condition(db, episode, "desconocida", message)
            if outside:
                state.inicio_recuperacion = None
                _condition(db, episode, "activa", message)
                deviation = abs(value - limit)
                severity = "critica" if deviation >= 5 else "alta" if deviation >= 2 else "media"
                levels = {"media": 0, "alta": 1, "critica": 2}
                if levels[severity] > levels[episode.severidad]:
                    record_action(db, episode, "escalada", message=message, observed=observed,
                        registered=aware(message.recibido_en), detail={"from": episode.severidad, "to": severity, "temperature_c": value})
                    episode.severidad = severity
            elif recovered:
                if state.inicio_recuperacion is None:
                    state.inicio_recuperacion = observed
                if observed - aware(state.inicio_recuperacion) >= HOLD:
                    episode.fin_condicion = observed
                    _condition(db, episode, "recuperada", message)
                    state.episodio_id = None
                    state.inicio_candidato = state.inicio_recuperacion = None
            else:
                state.inicio_recuperacion = None
            continue
        if not outside:
            state.inicio_candidato = None
            continue
        if state.inicio_candidato is None:
            state.inicio_candidato = observed
        if observed - aware(state.inicio_candidato) < HOLD:
            continue
        deviation = abs(value - limit)
        episode = m.EventoAlerta(dispositivo_id=message.dispositivo_id, fermentacion_id=process.id,
            tipo_alerta=code, severidad="critica" if deviation >= 5 else "alta" if deviation >= 2 else "media",
            estado="pendiente", met_dispar="regla_termica_v2", version_regla=RULE_VERSION, origen=message.origen,
            timestamp=aware(message.recibido_en), inicio_condicion=state.inicio_candidato,
            ultima_observacion=observed, estado_condicion="activa", valor_registrado=value, valor_limite=limit,
            mensaje=f"Temperatura {'sobre' if high else 'bajo'} el perfil durante al menos 10 minutos de observación.",
            evidencia={"configuration": config, "trigger_message_id": message.id, "temperature_c": value,
                       "condition_started_at": aware(state.inicio_candidato).isoformat(),
                       "confirmed_at": observed.isoformat(), "received_at": aware(message.recibido_en).isoformat(),
                       "quality": message.calidad_temperatura, "source": message.origen,
                       "interpretation": "Desviación térmica observada; no predicción de parada ni diagnóstico causal"})
        db.add(episode); db.flush()
        state.episodio_id = episode.id
        record_action(db, episode, "creada", message=message, detail=episode.evidencia,
                      observed=observed, registered=aware(message.recibido_en))


def close_process_conditions(db, process, actor):
    """Administrative process closure is not measured recovery or human resolution."""
    for state in db.query(m.EstadoRegla).filter_by(fermentacion_id=process.id).with_for_update():
        if state.episodio_id:
            episode = db.query(m.EventoAlerta).filter_by(id=state.episodio_id).with_for_update().one()
            from app.services.simulation_time import message_clock
            trigger_id = (episode.evidencia or {}).get('trigger_message_id')
            trigger = db.get(m.MensajeTelemetria, trigger_id) if trigger_id else None
            clock = message_clock(db, trigger) if trigger else None
            closed_real = aware(process.fecha_real_fin)
            closed_observed = clock.simulated_at(closed_real) if clock else closed_real
            episode.estado_condicion = "cerrada_proceso"
            episode.fin_condicion = closed_observed
            record_action(db, episode, "cerrada_proceso", actor=actor, observed=closed_observed,
                          registered=closed_real,
                          detail={"reason": "Proceso finalizado; no acredita recuperación de la señal",
                                  "closed_at_real": closed_real.isoformat(),
                                  "observation_clock": "simulated" if clock else "real",
                                  "simulation_clock": clock.model_dump(mode='json') if clock else None})
        state.episodio_id = None
        state.inicio_candidato = state.inicio_recuperacion = None
