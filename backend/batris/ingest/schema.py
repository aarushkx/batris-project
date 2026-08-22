"""
Common format for battery data.

Different data sources, like NASA files, CSV files, or BMS data,
can have different formats. We convert all of them into the same
format defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


@dataclass
class PhaseTelemetry:
    """
    Stores battery data collected during one charging or discharging phase.
    All arrays should have the same number of values and match the time array.
    """

    time_s: np.ndarray          # Time in seconds from the start of the phase
    voltage_v: np.ndarray       # Battery terminal voltage
    current_a: np.ndarray       # Current: positive for charging, negative for discharging
    temperature_c: np.ndarray   # Battery temperature

    def __post_init__(self):
        n = len(self.time_s)
        for name in ("voltage_v", "current_a", "temperature_c"):
            arr = getattr(self, name)
            if len(arr) != n:
                raise ValueError(
                    f"PhaseTelemetry.{name} has length {len(arr)}, expected {n} "
                    "to match time_s"
                )

    @property
    def duration_s(self) -> float:
        return float(self.time_s[-1] - self.time_s[0]) if len(self.time_s) > 1 else 0.0


@dataclass
class ImpedanceReading:
    """
    Electrochemical Impedance Spectroscopy (EIS) diagnostic snapshot.

    Stores an impedance measurement of the battery.

    `re_ohm` is the ohmic resistance and `rct_ohm` is the charge transfer resistance.
    These values can increase as the battery gets older.
    """

    re_ohm: float
    rct_ohm: float
    measured_at: Optional[datetime] = None

    @property
    def r_total_ohm(self) -> float:
        return self.re_ohm + self.rct_ohm


@dataclass
class CycleRecord:
    """
    Stores the data for one battery charge/discharge cycle.
    """

    battery_id: str
    format_key: str
    cycle_index: int                     # Cycle number, starting from 1
    timestamp: datetime                  # Time when the discharge started
    ambient_temp_c: float

    charge: Optional[PhaseTelemetry] = None
    discharge: Optional[PhaseTelemetry] = None
    impedance: Optional[ImpedanceReading] = None

    # Measured battery capacity from a controlled full discharge.
    # This is used as the actual/reference SOH value when training and checking the model.
    # It is never given to the model as an input.
    # Obtaining it requires lab equipment, which is precisely what this platform exists to avoid needing that.
    measured_capacity_ah: Optional[float] = None

    meta: dict = field(default_factory=dict)

    @property
    def has_full_telemetry(self) -> bool:
        # True when both charge and discharge data are available
        return self.charge is not None and self.discharge is not None
