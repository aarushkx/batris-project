"""
Handles user battery data and converts it into model-ready input.

Supports two input methods:
1. Telemetry upload: processes charge cycle data using the same feature
   extraction used during training.
2. Questionnaire input: converts user-provided values into model features.

Both methods return the feature data, selected tier and any assumptions made
during processing.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .features import SOH_FEATURES, build_feature_table
from .formats import BatteryFormat, get_format
from .ingest.schema import CycleRecord, ImpedanceReading, PhaseTelemetry
from .tiers import InputTier, best_tier_for, get_tier

logger = logging.getLogger(__name__)

# Average current during the constant-voltage charging phase.
# A default value is used only when the user does not provide real data.
# Any assumed value is reported clearly in the final result.
CV_MEAN_CURRENT_FRACTION = 0.30


class OnboardingError(ValueError):
    """Raised when user input cannot be turned into a usable feature row."""


# ===========================================================================
# Path 1: telemetry upload
# ===========================================================================

TELEMETRY_COLUMNS = {"time_s", "voltage_v", "current_a", "temperature_c"}


def from_telemetry_csv(
    csv_text: str,
    format_key: str,
    battery_id: str = "USER-BATTERY",
    ambient_temp_c: Optional[float] = None,
    re_ohm: Optional[float] = None,
    rct_ohm: Optional[float] = None,
) -> Tuple[pd.DataFrame, InputTier, List[str]]:
    """Build a feature row from an uploaded charge-cycle CSV.

    Required columns: ``time_s``, ``voltage_v``, ``current_a``,
    ``temperature_c``. An optional ``phase`` column is honoured; without it the
    rows are assumed to describe a single charge.
    """
    fmt = get_format(format_key)
    assumptions: List[str] = []

    try:
        df = pd.read_csv(io.StringIO(csv_text))
    except Exception as exc:
        raise OnboardingError(f"Could not parse the CSV: {exc}") from exc

    df.columns = [c.strip().lower() for c in df.columns]

    # Supports different common column names used in exported files.
    # This prevents valid battery data from being rejected due to header naming
    # differences.
    aliases = {
        "time": "time_s", "time_sec": "time_s", "seconds": "time_s",
        "elapsed_s": "time_s", "t": "time_s",
        "voltage": "voltage_v", "v": "voltage_v", "volts": "voltage_v",
        "current": "current_a", "i": "current_a", "amps": "current_a",
        "temperature": "temperature_c", "temp": "temperature_c",
        "temp_c": "temperature_c", "cell_temp": "temperature_c",
    }
    df = df.rename(
        columns={k: v for k, v in aliases.items() if k in df.columns})

    missing = TELEMETRY_COLUMNS - set(df.columns)
    if missing:
        raise OnboardingError(
            f"CSV is missing required columns: {sorted(missing)}. "
            f"Expected at least: {sorted(TELEMETRY_COLUMNS)}. "
            f"Found: {sorted(df.columns)}"
        )

    if "phase" in df.columns:
        df = df[df["phase"].astype(str).str.strip().str.lower() == "charge"]
        if df.empty:
            raise OnboardingError(
                "No rows with phase='charge' found in the CSV.")

    df = df[list(TELEMETRY_COLUMNS)].apply(
        pd.to_numeric, errors="coerce").dropna()
    if len(df) < 20:
        raise OnboardingError(
            f"Only {len(df)} usable samples after cleaning. At least 20 are "
            "needed to characterise the shape of a charge curve."
        )
    df = df.sort_values("time_s")

    current = df["current_a"].to_numpy(dtype=float)
    # Normalise the sign convention: some loggers report charging as negative.
    active = current[np.abs(current) > 0.02 * np.nanmax(np.abs(current))]
    if active.size and float(np.mean(active > 0)) < 0.5:
        current = -current
        assumptions.append(
            "Charging current was recorded as negative; the sign was inverted."
        )

    if ambient_temp_c is None:
        ambient_temp_c = float(df["temperature_c"].iloc[0])
        assumptions.append(
            f"Ambient temperature was not supplied; the first recorded cell "
            f"temperature ({ambient_temp_c:.1f} C) was used instead."
        )

    phase = PhaseTelemetry(
        time_s=df["time_s"].to_numpy(dtype=float),
        voltage_v=df["voltage_v"].to_numpy(dtype=float),
        current_a=current,
        temperature_c=df["temperature_c"].to_numpy(dtype=float),
    )

    impedance = None
    if re_ohm is not None and rct_ohm is not None:
        impedance = ImpedanceReading(
            re_ohm=float(re_ohm), rct_ohm=float(rct_ohm))

    record = CycleRecord(
        battery_id=battery_id,
        format_key=format_key,
        cycle_index=1,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        ambient_temp_c=float(ambient_temp_c),
        charge=phase,
        discharge=None,
        impedance=impedance,
        measured_capacity_ah=None,
        meta={"source": "user_upload"},
    )

    row = build_feature_table([record])
    _sanity_check_charge(row.iloc[0], fmt)

    available = {f for f in SOH_FEATURES if np.isfinite(
        row.iloc[0].get(f, np.nan))}
    tier = best_tier_for(available)
    logger.info("Uploaded telemetry resolved to tier %s", tier.key)
    return row, tier, assumptions


def _sanity_check_charge(row: pd.Series, fmt: BatteryFormat) -> None:
    """Checks if the uploaded battery data matches the selected format.

    Prevents incorrect inputs, such as wrong battery type or discharge data instead
    of charging data, from producing unreliable predictions.
    """
    cc = row.get("cc_capacity_frac", np.nan)
    if not np.isfinite(cc):
        raise OnboardingError(
            "Could not identify a constant-current charging phase in this data. "
            "Check that the file covers a charge (not a discharge) and that the "
            "current column is in amperes."
        )
    total = row.get("total_charge_frac", np.nan)
    if np.isfinite(total) and total > 1.6:
        raise OnboardingError(
            f"The data shows {total:.2f} times the rated capacity being delivered "
            f"in a single charge, which is not physically plausible for a "
            f"{fmt.rated_capacity_ah} Ah {fmt.display_name}. The selected battery "
            "format is probably wrong, or the current units are not amperes."
        )


# ===========================================================================
# Path 2: questionnaire
# ===========================================================================

def from_questionnaire(
    answers: Dict,
) -> Tuple[pd.DataFrame, InputTier, List[str]]:
    """Creates a feature row from user-provided charge summary data."""
    assumptions: List[str] = []

    format_key = answers.get("format_key")
    if not format_key:
        raise OnboardingError("A battery format must be selected.")
    fmt = get_format(format_key)

    def number(key: str, required: bool = False) -> Optional[float]:
        value = answers.get(key)
        if value in (None, "", "null"):
            if required:
                raise OnboardingError(f"'{key}' is required.")
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise OnboardingError(f"'{key}' must be a number, got {value!r}.")

    charge_current = number("charge_current_a", required=True)
    cc_minutes = number("cc_duration_min", required=True)
    cv_minutes = number("cv_duration_min", required=True)

    if charge_current <= 0:
        raise OnboardingError("Charging current must be greater than zero.")
    if cc_minutes <= 0:
        raise OnboardingError(
            "Time at steady current must be greater than zero.")
    if cv_minutes < 0:
        raise OnboardingError("Tapering time cannot be negative.")

    # -- charge throughput ---------------------------------------------------
    cc_ah = charge_current * (cc_minutes / 60.0)

    total_ah = number("total_charge_ah")
    total_kwh = number("total_charge_kwh")
    if total_ah is None and total_kwh is not None:
        total_ah = (total_kwh * 1000.0) / fmt.nominal_voltage_v
        assumptions.append(
            f"Energy of {total_kwh} kWh was converted to {total_ah:.2f} Ah using "
            f"the pack's {fmt.nominal_voltage_v} V nominal voltage."
        )

    if total_ah is None:
        # Estimates the tapering phase throughput.
        # This is the biggest assumption made when using questionnaire data.
        cv_ah = charge_current * CV_MEAN_CURRENT_FRACTION * (cv_minutes / 60.0)
        total_ah = cc_ah + cv_ah
        assumptions.append(
            f"Total charge delivered was not supplied. The tapering phase was "
            f"estimated at {CV_MEAN_CURRENT_FRACTION:.0%} of the steady current "
            f"on average, giving {total_ah:.2f} Ah overall. Supplying the actual "
            "figure from your charger would improve this estimate."
        )
    else:
        cv_ah = total_ah - cc_ah
        if cv_ah < 0:
            raise OnboardingError(
                f"The steady phase alone accounts for {cc_ah:.2f} Ah, which "
                f"exceeds the {total_ah:.2f} Ah total you entered. Check the "
                "current and duration figures."
            )

    if total_ah > 1.6 * fmt.rated_capacity_ah:
        raise OnboardingError(
            f"These figures imply {total_ah:.2f} Ah delivered into a "
            f"{fmt.rated_capacity_ah} Ah battery, which is not physically "
            "plausible. Check the current, duration and format selection."
        )

    # -- assemble the feature row -------------------------------------------
    peak_temp = number("peak_temp_c")
    ambient = number("ambient_temp_c")

    if ambient is None:
        ambient = 25.0
        assumptions.append(
            "Ambient temperature was not supplied; 25 C assumed.")
    if peak_temp is None:
        # Estimates temperature rise during charging.
        # A small temperature increase is assumed because charging generates heat,
        # and the assumption is clearly reported.
        peak_temp = ambient + 6.0
        assumptions.append(
            f"Peak battery temperature was not supplied; {peak_temp:.0f} C assumed "
            f"(6 C above ambient). Supplying the real figure would sharpen the "
            "thermal part of the assessment."
        )

    row = {name: np.nan for name in SOH_FEATURES}
    row.update({
        "cc_capacity_frac": cc_ah / fmt.rated_capacity_ah,
        "cv_capacity_frac": cv_ah / fmt.rated_capacity_ah,
        "cc_cv_ah_ratio": cc_ah / (cv_ah + 1e-9),
        "cc_time_fraction": cc_minutes / (cc_minutes + cv_minutes + 1e-9),
        "total_charge_frac": total_ah / fmt.rated_capacity_ah,
        "mean_charge_c_rate": fmt.to_c_rate(charge_current),
        "ch_temp_max_c": peak_temp,
        "ch_temp_mean_c": (peak_temp + ambient) / 2.0,
        "ch_temp_rise_c": max(0.0, peak_temp - ambient),
        "ch_frac_above_warn": 1.0 if peak_temp > fmt.temp_warn_c else 0.0,
        "ambient_temp_c": ambient,
    })

    # Optional EIS, if the user happens to have it.
    re_ohm = number("re_ohm")
    rct_ohm = number("rct_ohm")
    if re_ohm is not None and rct_ohm is not None:
        window = max(fmt.v_max - fmt.v_min, 1e-6)
        row["re_norm"] = re_ohm * fmt.rated_capacity_ah / window
        row["rct_norm"] = rct_ohm * fmt.rated_capacity_ah / window

    frame = pd.DataFrame([{
        "battery_id": answers.get("battery_id") or "USER-BATTERY",
        "format_key": format_key,
        # Cycle count is only used as extra information, not as a model feature.
        # If it is unknown, it stays empty instead of assuming a new battery.
        "cycle_index": number("cycle_count") if number("cycle_count") else np.nan,
        "timestamp": pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        "rated_capacity_ah": fmt.rated_capacity_ah,
        **row,
        # Optional user-supplied observations used by the safety rules only.
        "audit_min_voltage_v": number("min_voltage_seen_v") or np.nan,
        "audit_dis_temp_max_c": np.nan,
        "audit_mean_dis_c_rate": np.nan,
        "audit_capacity_ah": number("measured_capacity_ah") or np.nan,
    }])

    available = {f for f in SOH_FEATURES if np.isfinite(
        frame.iloc[0].get(f, np.nan))}
    tier = best_tier_for(available)
    logger.info("Questionnaire input resolved to tier %s", tier.key)
    return frame, tier, assumptions


# ===========================================================================
# Direct measurement
# ===========================================================================

def direct_measurement(measured_capacity_ah: float, format_key: str) -> Dict:
    """Calculates SOH from a real capacity test.

    This is a direct calculation, not a model prediction. If a measured capacity
    test is available, it is reported separately from estimated SOH values.
    """
    fmt = get_format(format_key)
    soh = measured_capacity_ah / fmt.rated_capacity_ah
    return {
        "method": "MEASURED",
        "method_description": (
            "State of health computed directly from a capacity measurement the "
            "user supplied. No model was involved. Accuracy depends entirely on "
            "how the measurement was taken; a full controlled discharge on "
            "calibrated equipment is required for this to be meaningful."
        ),
        "measured_capacity_ah": round(float(measured_capacity_ah), 4),
        "soh": round(float(soh), 4),
        "soh_percent": round(100 * float(soh), 2),
        "rated_capacity_ah": fmt.rated_capacity_ah,
    }
