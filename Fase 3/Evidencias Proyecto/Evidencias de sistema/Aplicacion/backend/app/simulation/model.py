"""Phase/thermal surrogate inspired by SmartBarrel; not an enological calibration.

All rates use hours. Noise affects observations, never the latent mass balance.
The fixed integration grid and per-sample RNG make restarts/retries reproducible.
"""
from datetime import timezone
import math
import random
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

MODEL_VERSION = "mosto-phases-1"
STEP_HOURS = 1 / 12  # five physical minutes; independent of HTTP polling
SCENARIOS = ("healthy", "cold_shock", "heat_stress", "nutrient_depletion", "slow")
PHASES = ("lag", "exponential", "stationary", "decline")


class SimulationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    model_version: Literal["mosto-phases-1"] = MODEL_VERSION
    process_id: int = Field(gt=0)
    process_start: AwareDatetime
    seed: int = Field(ge=0, le=2147483647, strict=True)
    scenario: Literal["healthy", "cold_shock", "heat_stress", "nutrient_depletion", "slow"]
    initial_brix: float = Field(default=24, ge=15, le=30)
    asymptote_brix: float = Field(default=-1, ge=-3, le=3)
    ambient_c: float = Field(default=21, ge=15, le=27)
    fault_at_hours: float = Field(default=60, ge=24, le=240)
    duration_hours: int = Field(default=336, ge=24, le=720, strict=True)
    cadence_seconds: Literal[300] = 300
    brix_noise_sd: float = Field(default=0.025, ge=0, le=0.15)
    temperature_noise_sd: float = Field(default=0.06, ge=0, le=0.5)

    @model_validator(mode="after")
    def normalize(self):
        object.__setattr__(self, "process_start", self.process_start.astimezone(timezone.utc))
        if self.scenario in {"cold_shock", "heat_stress", "nutrient_depletion"} and self.fault_at_hours >= self.duration_hours:
            raise ValueError("Fault onset must precede the simulation horizon")
        return self


def smoothstep(value, start, end):
    x = max(0.0, min(1.0, (value - start) / (end - start)))
    return x * x * (3 - 2 * x)


def phase_weights(hours):
    """Partition of unity with overlapping transitions around 20/70/150 h."""
    a = smoothstep(hours, 15, 25)
    b = smoothstep(hours, 65, 80)
    c = smoothstep(hours, 145, 170)
    return dict(zip(PHASES, (1 - a, a - b, b - c, c)))


def phase_at(hours):
    return max(phase_weights(hours), key=phase_weights(hours).get)


class Trajectory:
    """Cached deterministic latent evolution; no database, clock or network access."""
    def __init__(self, spec: SimulationSpec):
        self.spec = spec
        rng = random.Random(spec.seed)
        self.rate_scale = rng.uniform(0.88, 1.12)
        self.thermal_tau = rng.uniform(2.5, 4.0)
        self.ambient_phase = rng.uniform(0, 2 * math.pi)
        self.states = [(spec.initial_brix, spec.ambient_c, 1.0)]

    def _step(self, index):
        s = self.spec
        hours = (index - 0.5) * STEP_HOURS
        brix, temp, viability = self.states[-1]
        weights = phase_weights(hours)
        k = sum(w * rate for w, rate in zip(weights.values(), (0.0003, 0.020, 0.015, 0.004)))
        fault = smoothstep(hours, s.fault_at_hours, s.fault_at_hours + 6)
        target = s.ambient_c + 0.5 * math.sin(2 * math.pi * hours / 24 + self.ambient_phase)
        if s.scenario == "cold_shock":
            target -= 13 * fault
        elif s.scenario == "heat_stress":
            target += 17 * fault
        nutrients = 1 - 0.998 * fault if s.scenario == "nutrient_depletion" else 1
        speed = 0.30 if s.scenario == "slow" else 1
        # Smooth rate suppression, plus irreversible heat damage in this scenario.
        thermal_factor = math.exp(-((temp - 24) / 9) ** 2)
        damage = max(0, temp - 32) * 0.06
        viability *= math.exp(-damage * STEP_HOURS)
        effective_rate = k * self.rate_scale * thermal_factor * viability * nutrients * speed
        remaining = max(0, brix - s.asymptote_brix)
        next_brix = s.asymptote_brix + remaining * math.exp(-effective_rate * STEP_HOURS)
        consumed = brix - next_brix
        # Lumped heat balance: environmental exchange + heat proportional to consumption.
        next_temp = target + (temp - target) * math.exp(-STEP_HOURS / self.thermal_tau) + 1.5 * consumed
        self.states.append((next_brix, next_temp, viability))

    def sample(self, sequence):
        if isinstance(sequence, bool) or not isinstance(sequence, int) or not 0 <= sequence <= self.spec.duration_hours * 12:
            raise ValueError("Sequence outside simulation horizon")
        while len(self.states) <= sequence:
            self._step(len(self.states))
        brix, temp, viability = self.states[sequence]
        # Independent stream per index: network retries cannot change a reading.
        rng = random.Random(f"{MODEL_VERSION}:{self.spec.seed}:{sequence}")
        return {
            "brix_apparent": round(brix + rng.gauss(0, self.spec.brix_noise_sd), 4),
            "temperature_c": round(temp + rng.gauss(0, self.spec.temperature_noise_sd), 4),
            "latent_brix": brix, "latent_temperature": temp, "viability": viability,
            "phase": phase_at(sequence * STEP_HOURS),
            "phase_weights": phase_weights(sequence * STEP_HOURS),
        }
