"""Versioned observation/transport faults; never change the biological model."""
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Fault(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["brix_missing", "temperature_missing", "brix_frozen_unflagged",
                  "brix_drift_unflagged", "communication_outage", "delivery_delay", "message_loss"]
    start_sequence: int = Field(ge=0, le=8640, strict=True)
    end_sequence: int = Field(gt=0, le=8641, strict=True)
    drift_brix_per_hour: FiniteFloat | None = Field(default=None, ge=-.25, le=.25)
    delay_seconds: int | None = Field(default=None, gt=0, le=86400, strict=True)

    @model_validator(mode="after")
    def valid(self):
        if self.end_sequence <= self.start_sequence:
            raise ValueError("Fault interval must be positive and end-exclusive")
        if self.kind == "brix_frozen_unflagged" and self.start_sequence == 0:
            raise ValueError("A frozen sensor requires an earlier clean sample")
        if (self.kind == "brix_drift_unflagged") != (self.drift_brix_per_hour is not None):
            raise ValueError("Only drift faults require drift_brix_per_hour")
        if (self.kind == "delivery_delay") != (self.delay_seconds is not None):
            raise ValueError("Only delivery delays require delay_seconds")
        return self

    @property
    def channel(self):
        return "brix" if self.kind.startswith("brix_") else "temperature" if self.kind.startswith("temperature_") else "transport"


class FaultPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["emitter-faults-v1"] = "emitter-faults-v1"
    events: tuple[Fault, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unambiguous(self):
        ordered = sorted(self.events, key=lambda f: (f.start_sequence, f.end_sequence, f.kind))
        for index, fault in enumerate(ordered):
            if any(other.channel == fault.channel and other.start_sequence < fault.end_sequence
                   for other in ordered[index + 1:]):
                raise ValueError("Overlapping faults on the same channel/transport are ambiguous")
        object.__setattr__(self, "events", tuple(ordered))
        return self

    def validate_horizon(self, spec):
        if any(f.end_sequence > spec.duration_hours * 12 + 1 for f in self.events):
            raise ValueError("Fault extends beyond the simulation horizon")


def emission(trajectory, index, plan=None):
    sample = trajectory.sample(index)
    temperature = {"value": sample["temperature_c"], "quality": "good"}
    brix = {"value": sample["brix_apparent"], "quality": "good"}
    observed = trajectory.spec.process_start + timedelta(seconds=index * 300)
    available, lost, applied = observed, False, []
    for fault in plan.events if plan else ():
        if not fault.start_sequence <= index < fault.end_sequence:
            continue
        applied.append(fault.kind)
        if fault.kind == "brix_missing":
            brix = {"value": None, "quality": "missing"}
        elif fault.kind == "temperature_missing":
            temperature = {"value": None, "quality": "missing"}
        elif fault.kind == "brix_frozen_unflagged":
            brix["value"] = trajectory.sample(fault.start_sequence - 1)["brix_apparent"]
        elif fault.kind == "brix_drift_unflagged":
            brix["value"] += (index - fault.start_sequence) / 12 * fault.drift_brix_per_hour
        elif fault.kind == "communication_outage":
            available = trajectory.spec.process_start + timedelta(seconds=fault.end_sequence * 300)
        elif fault.kind == "delivery_delay":
            available = observed + timedelta(seconds=fault.delay_seconds)
        elif fault.kind == "message_loss":
            lost = True
    return temperature, brix, available, lost, {**sample, "emitter_faults": applied}


def outage_until(spec, plan, now):
    for fault in plan.events if plan else ():
        if fault.kind == "communication_outage":
            start = spec.process_start + timedelta(seconds=fault.start_sequence * 300)
            end = spec.process_start + timedelta(seconds=fault.end_sequence * 300)
            if start <= now < end:
                return end
    return None
