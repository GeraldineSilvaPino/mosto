from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app import models as m
from app.services.access import business_db
from app.services.telemetry_v2 import aware, utc_now
from app.services.simulation_time import process_clock_at, observation_end
from app.services.curve_comparison import curves, VERSION, VARIABLES, MAX_GAP_SECONDS, TELEMETRY_LIMIT, MANUAL_LIMIT

router = APIRouter(prefix='/api/procesos', tags=['Comparación de evidencia'])


@router.get('/{process_id}/comparacion')
def comparison(process_id: int, response: Response,
               variable: Literal['temperatura', 'brix_aparente', 'densidad', 'ph'] = 'brix_aparente',
               reference_id: int | None = Query(None, gt=0), hours: int = Query(24, ge=1, le=168),
               as_of: AwareDatetime | None = None, db: Session = Depends(business_db('operations'))):
    ids = [process_id] + ([reference_id] if reference_id is not None and reference_id != process_id else [])
    processes = []
    for ident in ids:
        process = db.query(m.ProcesoFermentacion).filter_by(id=ident).first()
        if process is None:
            raise HTTPException(404, 'Proceso inexistente o fuera del ámbito autorizado')
        processes.append(process)
    now = utc_now()
    cutoff = (as_of or now).astimezone(timezone.utc)
    if cutoff > now or any(cutoff < aware(p.fecha_inicio) for p in processes):
        raise HTTPException(422, 'Corte fuera del historial disponible de los procesos')
    main = processes[0]
    clocks = [process_clock_at(db, p.id, cutoff) for p in processes]
    end = observation_end(main, cutoff, clocks[0])
    age_end = max(0, (end - aware(main.fecha_inicio)).total_seconds() / 3600)
    age_start = max(0, age_end - hours)
    response.headers['Cache-Control'] = 'no-store'
    return dict(version=VERSION, as_of=cutoff, alignment='hours_since_process_start', variable=variable,
        unit=VARIABLES[variable][0], age_start=age_start, age_end=age_end,
        max_gap_seconds=MAX_GAP_SECONDS, limits=dict(telemetry=TELEMETRY_LIMIT, manual=MANUAL_LIMIT),
        processes=[curves(db, p, variable, age_start, age_end, cutoff, clock=clock, hours=hours)
                   for p, clock in zip(processes, clocks)],
        interpretation='comparacion_descriptiva', estado_ia='NO_VALIDADO', riesgo_pct=None,
        recommendations=[], warning='Las diferencias no identifican causas ni validan tratamientos. Brix aparente no equivale a azúcar residual.')
