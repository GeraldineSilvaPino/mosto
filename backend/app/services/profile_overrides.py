"""Effective thermal parameters by observation time; original snapshots stay immutable."""
from app import models as m
from app.services.profile_versions import effective_profile
from app.services.telemetry_v2 import aware


def adjustment_at(db, process_id, at):
    return db.query(m.AjustePerfilProceso).filter(
        m.AjustePerfilProceso.fermentacion_id == process_id,
        m.AjustePerfilProceso.vigente_desde <= at).order_by(m.AjustePerfilProceso.revision.desc()).first()


def applied_profile(db, process, profile, at):
    adjustment = adjustment_at(db, process.id, at)
    base = dict(effective_profile(process, profile))
    if adjustment:
        base = {**adjustment.configuracion, 'override_revision': adjustment.revision,
                'override_id': adjustment.id, 'override_actor_id': adjustment.usuario_id,
                'override_effective_at': aware(adjustment.vigente_desde).isoformat()}
    return base


def thermal_configuration(base, adjustment):
    if adjustment is None:
        return dict(base)
    low, high = adjustment.configuracion['temp_min'], adjustment.configuracion['temp_max']
    return {**base, 'temp_min': low, 'temp_max': high,
            'hysteresis_c': min(.5, max(0, (high - low) / 4)),
            'override_id': adjustment.id, 'override_revision': adjustment.revision,
            'override_actor_id': adjustment.usuario_id,
            'override_effective_at': aware(adjustment.vigente_desde).isoformat()}
