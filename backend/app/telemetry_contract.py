"""Public v2 transport and provisioning contracts; no client-owned tenant/source."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from app.simulation.model import SimulationSpec


class ChannelReading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: FiniteFloat | None
    quality: Literal["good", "missing", "invalid", "uncalibrated"]

    @model_validator(mode="after")
    def validate_quality(self):
        if self.quality == "good" and self.value is None:
            raise ValueError("A good reading requires a measured value")
        if self.quality == "missing" and self.value is not None:
            raise ValueError("A missing reading cannot contain an invented value")
        return self


class TelemetryV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2]
    device_id: int = Field(gt=0)
    boot_id: UUID
    sequence: int = Field(ge=0, le=9223372036854775807, strict=True)
    observed_at: AwareDatetime
    temperature_c: ChannelReading
    brix_apparent: ChannelReading
    calibration_id: int | None = Field(default=None, gt=0)
    tilt_degrees: FiniteFloat | None = Field(default=None, ge=0, le=180)

    @model_validator(mode="after")
    def normalize_measurement(self):
        self.observed_at = self.observed_at.astimezone(timezone.utc)
        if self.brix_apparent.quality == "good" and self.calibration_id is None:
            raise ValueError("Valid apparent Brix requires a calibration reference")
        return self


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: Literal["fisico", "simulado"]
    label: str = Field(min_length=1, max_length=80)
    expires_days: int = Field(default=90, ge=1, le=365, strict=True)


class CalibrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: str = Field(min_length=1, max_length=80)
    method: Literal["tilt_polynomial", "synthetic_identity"]
    valid_from: AwareDatetime
    valid_until: AwareDatetime | None = None
    coefficients: list[FiniteFloat] = Field(default_factory=list, max_length=4)
    tilt_min: FiniteFloat | None = Field(default=None, ge=0, le=180)
    tilt_max: FiniteFloat | None = Field(default=None, ge=0, le=180)
    temperature_coefficient: FiniteFloat = 0
    reference_temperature: FiniteFloat = 20
    tolerance: FiniteFloat = Field(default=0.1, ge=0, le=1)
    simulation: SimulationSpec | None = None

    @model_validator(mode="after")
    def validate_calibration(self):
        self.valid_from = self.valid_from.astimezone(timezone.utc)
        if self.valid_until is not None:
            self.valid_until = self.valid_until.astimezone(timezone.utc)
            if self.valid_until <= self.valid_from:
                raise ValueError("Calibration interval must be positive")
        if self.method == "tilt_polynomial":
            if self.simulation is not None:
                raise ValueError("Physical calibration cannot declare a synthetic trajectory")
            if not 2 <= len(self.coefficients) <= 4:
                raise ValueError("A physical calibration needs 2 to 4 polynomial coefficients")
            if self.tilt_min is None or self.tilt_max is None or self.tilt_min >= self.tilt_max:
                raise ValueError("A physical calibration needs an explicit valid tilt interval")
        elif self.coefficients or self.tilt_min is not None or self.tilt_max is not None or self.temperature_coefficient:
            raise ValueError("Synthetic calibration cannot declare a physical conversion")
        return self


class TelemetryAccepted(BaseModel):
    message_id: int
    duplicate: bool
    device_id: int
    process_id: int
    source: Literal["fisico", "simulado"]
    observed_at: datetime
    received_at: datetime
    temperature_c: ChannelReading
    brix_apparent: ChannelReading
    out_of_order: bool
    delayed: bool
    diagnostics: list[str]
