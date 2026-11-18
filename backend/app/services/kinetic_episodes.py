"""Opt-in synthetic kinetic episodes; never a learned probability or real-wine diagnosis."""
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import models as m
from app.services import episodes
from app.services.kinetics_query import process_kinetics
from app.services.telemetry_v2 import aware

CODE = "brix_ralentizacion"
VERSION = "kinetic-episodes-v1"


class KineticRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    version: Literal["kinetic-episodes-v1"] = VERSION
    scope: Literal["experimental_simulado"] = "experimental_simulado"
    recent_slope_threshold: float = Field(default=-.015, ge=-.1, le=0)
    prior_slope_threshold: float = Field(default=-.04, ge=-1, lt=0)
    recovery_slope_threshold: float = Field(default=-.03, ge=-1, lt=0)
    minimum_brix: float = Field(default=5, ge=0, le=15)
    minimum_age_hours: float = Field(default=24, ge=24, le=72)
    hold_minutes: int = Field(default=60, ge=30, le=360)
    recovery_minutes: int = Field(default=60, ge=30, le=360)
    max_gap_minutes: Literal[15] = 15

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if not self.prior_slope_threshold < self.recent_slope_threshold:
            raise ValueError("La pendiente previa debe ser menor que el umbral reciente")
        if not self.recovery_slope_threshold < self.recent_slope_threshold:
            raise ValueError("La recuperación requiere histéresis respecto de la entrada")
        return self


def rule_status(db, process_id):
    state = db.query(m.EstadoRegla).filter_by(fermentacion_id=process_id, codigo=CODE).first()
    if state is None:
        return {"configured": False, "status": "sin_configurar", "configuration": None}
    return {"configured": True, "status": "experimental_simulado",
            "configuration": state.configuracion, "episode_id": state.episodio_id,
            "last_observation": aware(state.ultima_observacion).isoformat(),
            "candidate_since": aware(state.inicio_candidato).isoformat() if state.inicio_candidato else None,
            "recovery_since": aware(state.inicio_recuperacion).isoformat() if state.inicio_recuperacion else None}


def evaluate_kinetic(db, process, message):
    """Under ingestion's tank lock, after flush; receipt-time causal snapshot.

    Configuration activation is a watermark. No replay before activation; no
    hidden defaults; immutable snapshot; audit and telemetry share a transaction.
    """
    if process.fecha_real_fin is not None or message.origen != "simulado":
        return
    state = db.query(m.EstadoRegla).filter_by(fermentacion_id=process.id, codigo=CODE).with_for_update().first()
    if state is None:
        return
    observed, received = aware(message.observado_en), aware(message.recibido_en)
    previous = aware(state.ultima_observacion)
    if observed <= previous:
        return
    config = state.configuracion
    gap = observed - previous > timedelta(minutes=config["max_gap_minutes"])
    state.ultima_observacion = observed
    episode = db.query(m.EventoAlerta).filter_by(id=state.episodio_id).with_for_update().first() if state.episodio_id else None
    snapshot = process_kinetics(db, process, received)
    features = snapshot["features"]
    # Brix quality is independent: a missing thermal channel is not a veto.
    usable = (features["brix_slope_6h"] is not None
              and message.calidad_brix == "good" and message.brix is not None
              and observed <= received
              and received - observed <= timedelta(minutes=15)
              and features["age_hours"] >= config["minimum_age_hours"]
              and features["brix_mean_1h"] > config["minimum_brix"])
    if gap or not usable:
        state.inicio_candidato = state.inicio_recuperacion = None
        if episode:
            episode.ultima_observacion = observed
            episodes._condition(db, episode, "desconocida", message)
        if not usable:
            return
    value = features["brix_slope_6h"]
    outside = value > config["recent_slope_threshold"]
    recovered = value <= config["recovery_slope_threshold"]
    if episode:
        episode.ultima_observacion = observed
        if outside:
            state.inicio_recuperacion = None
            episodes._condition(db, episode, "activa", message)
        elif recovered:
            if state.inicio_recuperacion is None:
                state.inicio_recuperacion = observed
            if observed - aware(state.inicio_recuperacion) >= timedelta(minutes=config["recovery_minutes"]):
                episode.fin_condicion = observed
                episodes._condition(db, episode, "recuperada", message)
                episodes.record_action(db, episode, "evidencia_recuperacion", message=message,
                    observed=observed, registered=received, detail={"features": features, "channels": snapshot["channels"]})
                state.episodio_id = None
                state.inicio_candidato = state.inicio_recuperacion = None
        else:
            state.inicio_recuperacion = None
        return
    if not outside or features["brix_slope_24h"] >= config["prior_slope_threshold"]:
        state.inicio_candidato = None
        return
    if state.inicio_candidato is None:
        state.inicio_candidato = observed
    if observed - aware(state.inicio_candidato) < timedelta(minutes=config["hold_minutes"]):
        return
    evidence = {"configuration": config, "trigger_message_id": message.id,
                "features": features, "channels": snapshot["channels"],
                "feature_version": snapshot["version"], "window_start": snapshot["window_start"],
                "condition_started_at": aware(state.inicio_candidato).isoformat(),
                "confirmed_at": observed.isoformat(), "received_at": received.isoformat(),
                "as_of": snapshot["as_of"], "source": message.origen,
                "interpretation": "Ralentización persistente de Brix aparente simulado; no parada confirmada ni diagnóstico causal"}
    episode = m.EventoAlerta(dispositivo_id=message.dispositivo_id, fermentacion_id=process.id,
        tipo_alerta=CODE, severidad="media", estado="pendiente", met_dispar="regla_cinetica_v2",
        version_regla=VERSION, origen=message.origen, timestamp=received,
        inicio_condicion=state.inicio_candidato, ultima_observacion=observed,
        estado_condicion="activa", valor_registrado=value, valor_limite=config["recent_slope_threshold"],
        mensaje="Ralentización observada de Brix aparente en simulación; revisar cobertura y evolución, sin inferir una causa.",
        evidencia=evidence)
    db.add(episode)
    db.flush()
    state.episodio_id = episode.id
    episodes.record_action(db, episode, "creada", message=message, detail=evidence,
                          observed=observed, registered=received)
