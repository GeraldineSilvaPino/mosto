"""Explicit clock conversion; integration must keep reception in real UTC.

This primitive alone does not authorize accelerated telemetry ingestion.
"""
from datetime import datetime, timedelta, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class SimulationClock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    real_anchor: AwareDatetime
    simulated_anchor: AwareDatetime
    factor: float = Field(default=1, ge=1, le=3600)

    @model_validator(mode="after")
    def normalize(self):
        for name in ("real_anchor", "simulated_anchor"):
            object.__setattr__(self, name, getattr(self, name).astimezone(timezone.utc))
        return self

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Clock timestamps require an explicit timezone")
        return value.astimezone(timezone.utc)

    def simulated_at(self, real_time: datetime) -> datetime:
        return self.simulated_anchor + (self._utc(real_time) - self.real_anchor) * self.factor

    def real_at(self, simulated_time: datetime) -> datetime:
        return self.real_anchor + (self._utc(simulated_time) - self.simulated_anchor) / self.factor

    def delivery_at(self, simulated_time: datetime, delay_seconds: float = 0) -> datetime:
        """Transport delay is real elapsed time, never accelerated biology."""
        import math
        if not math.isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("Transport delay must be finite and nonnegative")
        return self.real_at(simulated_time) + timedelta(seconds=delay_seconds)
