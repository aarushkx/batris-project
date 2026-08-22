"""
Generic CSV telemetry adapter.

This file is used to read battery data from normal CSV files.

Different battery data sources can have different formats. This adapter
takes a simple CSV format and converts it into the format used by our project.

The CSV can contain data from a BMS, battery testing setup, or other
battery data logger.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from ..formats import get_format
from .schema import CycleRecord, ImpedanceReading, PhaseTelemetry

logger = logging.getLogger(__name__)


# These columns must be present in every CSV file.
REQUIRED_COLUMNS = {
    "battery_id", "cycle_index", "phase", "timestamp",
    "time_s", "voltage_v", "current_a", "temperature_c",
}


def _build_phase(group: pd.DataFrame, expect_charging: bool) -> PhaseTelemetry | None:
    """Create phase data and fix the current sign if needed."""

    # Sort the data according to time.
    group = group.sort_values("time_s")

    # Ignore the phase if it has too few data points.
    if len(group) < 10:
        return None

    current = group["current_a"].to_numpy(dtype=float)

    # Check the current values to understand how the CSV represents
    # charging and discharging.
    # Some datasets use positive current for charging while others
    # use negative current. If the sign is opposite to what we expect,
    # we flip it.
    active = current[
        np.abs(current) > 0.01 * np.nanmax(np.abs(current) + 1e-9)
    ]

    if active.size:
        mostly_positive = float(np.mean(active > 0)) > 0.5

        # If the current sign is opposite, change it.
        if mostly_positive != expect_charging:
            current = -current

    # Store all the phase data in our common format.
    return PhaseTelemetry(
        time_s=group["time_s"].to_numpy(dtype=float),
        voltage_v=group["voltage_v"].to_numpy(dtype=float),
        current_a=current,
        temperature_c=group["temperature_c"].to_numpy(dtype=float),
    )


def load_csv(
    csv_path: Path | str,
    format_key: str,
) -> List[CycleRecord]:
    """Read one CSV file and convert it into CycleRecords."""

    csv_path = Path(csv_path)

    # Read the CSV file.
    df = pd.read_csv(csv_path)

    # Convert timestamp values into proper datetime values.
    # Invalid timestamps are converted to NaT.
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
        format="mixed"
    )

    # Check if any required columns are missing.
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"{csv_path.name} is missing required columns: {sorted(missing)}. "
            f"Expected schema: {sorted(REQUIRED_COLUMNS)}"
        )

    # Get the battery format and make sure the format key is valid.
    fmt = get_format(format_key)

    # Make phase names consistent.
    # For example, " Charge " becomes "charge".
    df["phase"] = df["phase"].str.strip().str.lower()

    records: List[CycleRecord] = []

    # Keep track of how many phases had their current sign changed.
    flipped_phases = 0

    # Group the data by battery and cycle number.
    for (battery_id, cycle_index), cycle_group in df.groupby(
        ["battery_id", "cycle_index"], sort=True
    ):

        # Get the charging and discharging rows separately.
        charge_rows = cycle_group[cycle_group["phase"] == "charge"]
        discharge_rows = cycle_group[cycle_group["phase"] == "discharge"]

        # Create the charge phase data.
        charge = (
            _build_phase(charge_rows, expect_charging=True)
            if len(charge_rows)
            else None
        )

        # Create the discharge phase data.
        discharge = (
            _build_phase(discharge_rows, expect_charging=False)
            if len(discharge_rows)
            else None
        )

        # Skip this cycle if there is no valid charge or discharge data.
        if charge is None and discharge is None:
            continue

        # Get the measured capacity if the CSV contains it.
        capacity = np.nan

        if "capacity_ah" in cycle_group.columns:
            values = cycle_group["capacity_ah"].dropna()

            if len(values):
                capacity = float(values.iloc[0])

        # If capacity is not given in the CSV, calculate it from
        # the discharge current and time.
        # This is called coulomb counting.
        if not np.isfinite(capacity) and discharge is not None:
            capacity = float(
                np.trapezoid(
                    np.abs(discharge.current_a),
                    discharge.time_s
                ) / 3600.0
            )

        # Read impedance data if it is available.
        impedance = None

        if {"re_ohm", "rct_ohm"} <= set(cycle_group.columns):
            eis = cycle_group[["re_ohm", "rct_ohm"]].dropna()

            if len(eis):
                impedance = ImpedanceReading(
                    re_ohm=float(eis["re_ohm"].iloc[0]),
                    rct_ohm=float(eis["rct_ohm"].iloc[0]),
                )

        # Use 25°C as the default ambient temperature.
        ambient = 25.0

        # If ambient temperature is available, use that value instead.
        if "ambient_temp_c" in cycle_group.columns:
            values = cycle_group["ambient_temp_c"].dropna()

            if len(values):
                ambient = float(values.iloc[0])

        # Create one CycleRecord containing all the information
        # about this battery cycle.
        records.append(
            CycleRecord(
                battery_id=str(battery_id),
                format_key=format_key,
                cycle_index=int(cycle_index),
                timestamp=pd.Timestamp(
                    cycle_group["timestamp"].min()
                ).to_pydatetime(),
                ambient_temp_c=ambient,
                charge=charge,
                discharge=discharge,
                impedance=impedance,

                # Only store capacity if it is a valid positive value.
                measured_capacity_ah=(
                    capacity
                    if np.isfinite(capacity) and capacity > 0
                    else None
                ),

                # Store some basic information about where the data came from.
                meta={
                    "source": "generic_csv",
                    "file": csv_path.name
                },
            )
        )

    # Show a warning if any current signs were corrected.
    if flipped_phases:
        logger.warning(
            "%s: corrected the current sign convention on %d phases",
            csv_path.name,
            flipped_phases,
        )

    # Print information about the loaded file.
    logger.info(
        "%s: loaded %d cycles (format=%s, %.1f Ah rated)",
        csv_path.name,
        len(records),
        format_key,
        fmt.rated_capacity_ah
    )

    return records


def load_csv_directory(
    data_dir: Path | str,
    format_key: str,
) -> List[CycleRecord]:
    """Read all CSV files from a directory."""

    data_dir = Path(data_dir)

    # Check if the directory exists.
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Directory {data_dir} not found"
        )

    # Find all CSV files in the directory.
    files = sorted(data_dir.glob("*.csv"))

    # Stop if there are no CSV files.
    if not files:
        raise FileNotFoundError(
            f"No CSV files found in {data_dir}"
        )

    records: List[CycleRecord] = []

    # Read each CSV file and add its battery cycles to the list.
    for path in files:
        records.extend(
            load_csv(path, format_key=format_key)
        )

    return records
