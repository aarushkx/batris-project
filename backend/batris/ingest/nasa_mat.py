"""
Adapter for reading the NASA Ames battery dataset.

The NASA dataset stores battery data in MATLAB (.mat) files.
This file reads those files and converts the data into the common
CycleRecord format used by the project.

Each MATLAB file contains charge, discharge and impedance data.
We use the discharge data as one battery cycle and also keep the
charge and latest impedance data connected to it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
from scipy.io import loadmat

from .schema import CycleRecord, ImpedanceReading, PhaseTelemetry

logger = logging.getLogger(__name__)


def _as_1d(value) -> np.ndarray:
    """Convert a MATLAB value into a simple 1D float array."""
    return np.atleast_1d(np.asarray(value, dtype=float)).ravel()


def _as_scalar(value) -> float:
    """Get one number from a MATLAB value."""
    arr = _as_1d(value)
    return float(arr[0]) if arr.size else float("nan")


def _parse_matlab_time(raw) -> Optional[datetime]:
    """Convert NASA's time format into a normal Python datetime."""

    # NASA stores time like:
    # [year, month, day, hour, minute, second]
    # The seconds value can also contain decimals.
    try:
        t = _as_1d(raw)

        if t.size < 6:
            return None

        year, month, day, hour, minute = (
            int(t[i]) for i in range(5)
        )

        seconds = float(t[5])

        # Create the date first and then add the seconds.
        base = datetime(year, month, day, hour, minute, 0)

        return base + timedelta(seconds=seconds)

    except (ValueError, TypeError, IndexError):
        return None


def _phase_from_matlab(data: dict) -> Optional[PhaseTelemetry]:
    """Convert charge or discharge data into PhaseTelemetry."""

    # These values are needed to create the phase data.
    required = (
        "Time",
        "Voltage_measured",
        "Current_measured",
        "Temperature_measured",
    )

    if not all(k in data for k in required):
        return None

    # Get the main battery measurements.
    time_s = _as_1d(data["Time"])
    voltage = _as_1d(data["Voltage_measured"])
    current = _as_1d(data["Current_measured"])
    temperature = _as_1d(data["Temperature_measured"])

    # Sometimes the arrays do not have the same length.
    # Use only the number of samples available in all arrays.
    n = min(
        len(time_s),
        len(voltage),
        len(current),
        len(temperature)
    )

    # Ignore phases with too little data.
    if n < 10:
        return None

    return PhaseTelemetry(
        time_s=time_s[:n],
        voltage_v=voltage[:n],
        current_a=current[:n],
        temperature_c=temperature[:n],
    )


def _impedance_from_matlab(data: dict) -> Optional[ImpedanceReading]:
    """Get resistance values from the NASA impedance data."""

    # Check if both resistance values are present.
    if "Re" not in data or "Rct" not in data:
        return None

    try:
        # The values can be complex, so we only use the real part.
        re_ohm = float(
            np.real(np.atleast_1d(data["Re"]).ravel()[0])
        )

        rct_ohm = float(
            np.real(np.atleast_1d(data["Rct"]).ravel()[0])
        )

    except (ValueError, TypeError, IndexError):
        return None

    # Ignore values that are not physically reasonable.
    if not (0.0 < re_ohm < 1.0) or not (0.0 < rct_ohm < 10.0):
        return None

    return ImpedanceReading(
        re_ohm=re_ohm,
        rct_ohm=rct_ohm
    )


def load_battery(
    mat_path: Path | str,
    format_key: str = "NASA_18650_LCO_2AH",
) -> List[CycleRecord]:
    """Read one NASA .mat battery file."""

    mat_path = Path(mat_path)

    # Use the filename as the battery ID.
    battery_id = mat_path.stem

    # Read the MATLAB file.
    raw = loadmat(
        str(mat_path),
        simplify_cells=True
    )

    # Find the actual battery data inside the file.
    data_keys = [
        k for k in raw
        if not k.startswith("__")
    ]

    if not data_keys:
        raise ValueError(
            f"{mat_path} contains no battery struct"
        )

    # Usually the battery ID is the key, otherwise use the first key.
    key = (
        battery_id
        if battery_id in raw
        else data_keys[0]
    )

    # Get all the battery operations.
    operations = raw[key]["cycle"]

    records: List[CycleRecord] = []

    # Store the charge that comes before a discharge.
    pending_charge: Optional[PhaseTelemetry] = None

    # Keep the latest impedance reading.
    latest_impedance: Optional[ImpedanceReading] = None

    cycle_index = 0

    # Go through all operations in the order they appear in the file.
    for op in operations:

        op_type = op.get("type", "unknown")

        # Convert bytes into a normal string if needed.
        if isinstance(op_type, bytes):
            op_type = op_type.decode("utf-8")

        op_type = str(op_type).strip()

        data = op.get("data", {})

        if not isinstance(data, dict):
            continue

        # -------------------------
        # CHARGE
        # -------------------------
        if op_type == "charge":

            # Save the latest charge because it should belong
            # to the next discharge cycle.
            phase = _phase_from_matlab(data)

            if phase is not None:
                pending_charge = phase

        # -------------------------
        # IMPEDANCE
        # -------------------------
        elif op_type == "impedance":

            # Read the resistance values.
            reading = _impedance_from_matlab(data)

            if reading is not None:

                # Save the time when the impedance was measured.
                reading.measured_at = _parse_matlab_time(
                    op.get("time")
                )

                latest_impedance = reading

        # -------------------------
        # DISCHARGE
        # -------------------------
        elif op_type == "discharge":

            # Convert discharge data into our common format.
            phase = _phase_from_matlab(data)

            if phase is None:
                continue

            # NASA directly provides the discharged capacity.
            # This will be used as the capacity/label for this cycle.
            capacity = _as_scalar(
                data.get("Capacity", np.nan)
            )

            # Ignore invalid capacity values.
            if not np.isfinite(capacity) or capacity <= 0:
                logger.debug(
                    "%s: skipping discharge with invalid capacity",
                    battery_id
                )

                pending_charge = None
                continue

            # We found a valid battery cycle.
            cycle_index += 1

            # Create one CycleRecord for this discharge cycle.
            records.append(
                CycleRecord(
                    battery_id=battery_id,
                    format_key=format_key,
                    cycle_index=cycle_index,

                    # Use the discharge time as the cycle timestamp.
                    timestamp=(
                        _parse_matlab_time(op.get("time"))
                        or datetime(2008, 1, 1)
                    ),

                    ambient_temp_c=float(
                        op.get("ambient_temperature", 24.0)
                    ),

                    # Add the charge that happened before this discharge.
                    charge=pending_charge,

                    # Add the current discharge data.
                    discharge=phase,

                    # Add the latest impedance measurement.
                    impedance=latest_impedance,

                    # Store the measured capacity.
                    measured_capacity_ah=capacity,

                    # Store where the data came from.
                    meta={
                        "source": "NASA_PCoE",
                        "file": mat_path.name
                    },
                )
            )

            # The saved charge has now been used for this cycle.
            pending_charge = None

    logger.info(
        "%s: loaded %d discharge cycles",
        battery_id,
        len(records)
    )

    return records


def load_directory(
    data_dir: Path | str,
    format_key: str = "NASA_18650_LCO_2AH",
) -> List[CycleRecord]:
    """Read all NASA .mat battery files from a directory."""

    data_dir = Path(data_dir)

    # Check if the directory exists.
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Data directory {data_dir} not found. "
            "See data/README.md for download instructions."
        )

    # Find all NASA battery files.
    mat_files = sorted(
        data_dir.glob("B*.mat")
    )

    if not mat_files:
        raise FileNotFoundError(
            f"No B*.mat battery files found in {data_dir}"
        )

    records: List[CycleRecord] = []

    # Read every battery file and add its cycles to the list.
    for path in mat_files:
        records.extend(
            load_battery(
                path,
                format_key=format_key
            )
        )

    return records
