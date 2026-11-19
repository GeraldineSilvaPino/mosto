"""Frozen full profile parameters, distinct from experimental kinetic policy."""
from fastapi import HTTPException
from app import models as m
from app.services.telemetry_v2 import utc_now

FIELDS = ("nomb_perfil", "temp_min", "temp_max", "ph_min", "ph_max",
          "brix_caida_min_dia", "cepa_id", "bodega_id", "activo")
NUMERIC = {"temp_min", "temp_max", "ph_min", "ph_max", "brix_caida_min_dia"}


def snapshot(profile):
    return {"profile_id": profile.id, "revision": profile.revision,
            **{name: float(getattr(profile, name)) if name in NUMERIC and getattr(profile, name) is not None
               else getattr(profile, name) for name in FIELDS}}


def record_version(db, profile, actor=None, origin="captura_existente"):
    value = snapshot(profile)
    existing = db.query(m.VersionPerfil).filter_by(perfil_id=profile.id, revision=profile.revision).first()
    if existing:
        if existing.configuracion != value:
            raise HTTPException(409, "El perfil cambió fuera del flujo versionado; requiere reconciliación explícita")
        return existing
    row = m.VersionPerfil(perfil_id=profile.id, revision=profile.revision, configuracion=value,
                          registrado_en=utc_now(), usuario_id=actor, origen=origin)
    db.add(row)
    db.flush()
    return row


def effective_profile(process, profile):
    return process.perfil_snapshot if process.perfil_snapshot is not None else snapshot(profile) if profile else {}
