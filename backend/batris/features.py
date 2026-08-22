"""
Feature extraction for each battery cycle.

This file takes the raw battery cycle data and creates useful features
that can be used by the SOH prediction model.

Important:
- Features used by the SOH model are calculated without using the full
  discharge results.
- Features starting with "audit_" come from the discharge and are only
  used as reference values/labels.

This separation is important because using the actual discharge capacity
as an input to predict SOH would make the prediction unfair.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .formats import BatteryFormat, get_format
from .ingest.schema import CycleRecord, PhaseTelemetry

logger = logging.getLogger(__name__)

EPS = 1e-9


# Different features are grouped based on what type of battery ageing
# they are trying to describe.
FEATURE_GROUPS: Dict[str, List[str]] = {
    "charge_acceptance": [
        "cc_capacity_frac",
        "cv_capacity_frac",
        "cc_cv_ah_ratio",
        "cc_time_fraction",
        "total_charge_frac",
        "charge_time_1c_equiv",
        "mean_charge_c_rate",
        "dvdt_cc_per_frac",
        "v_norm_at_cc_end",
    ],

    "internal_resistance": [
        "ohmic_r_norm",
        "re_norm",
        "rct_norm",
        "re_growth_ratio",
        "rct_growth_ratio",
    ],

    "thermal_stress": [
        "ch_temp_max_c",
        "ch_temp_rise_c",
        "ch_temp_mean_c",
        "ch_thermal_dose_c_h",
        "ch_frac_above_warn",
        "ambient_temp_c",
    ],

    "usage_history": [
        "cycle_index",
        "equivalent_full_cycles",
        "calendar_age_days",
        "mean_rest_h",
        "cum_thermal_dose_c_h",
    ],
}


# List of all features that the SOH model is allowed to use.
SOH_FEATURES: List[str] = [
    f
    for group in FEATURE_GROUPS.values()
    for f in group
]


# Some features may not work well in every situation.
# These groups help decide which features are safe to use.
#
# Some features depend on the charging setup.
PROTOCOL_DEPENDENT: set = {
    "mean_charge_c_rate",
    "charge_time_1c_equiv",
    "total_charge_frac",
}


# These features need data from when the battery was new.
REQUIRES_BASELINE: set = {
    "re_growth_ratio",
    "rct_growth_ratio",
}


# These features need battery history over time.
REQUIRES_HISTORY: set = set(
    FEATURE_GROUPS["usage_history"]
)


# Friendly names shown in the UI.
FEATURE_LABELS: Dict[str, str] = {
    "cc_capacity_frac": "Charge accepted in constant-current phase",
    "cv_capacity_frac": "Charge accepted in constant-voltage phase",
    "cc_cv_ah_ratio": "CC-to-CV charge ratio",
    "cc_time_fraction": "Constant-current time share",
    "total_charge_frac": "Total charge accepted",
    "charge_time_1c_equiv": "Normalised charge duration",
    "mean_charge_c_rate": "Average charging C-rate",
    "dvdt_cc_per_frac": "Charge-curve steepness",
    "v_norm_at_cc_end": "Voltage at end of constant-current phase",
    "ohmic_r_norm": "In-situ ohmic resistance",
    "re_norm": "Electrolyte resistance (EIS)",
    "rct_norm": "Charge-transfer resistance (EIS)",
    "re_growth_ratio": "Electrolyte resistance growth vs new",
    "rct_growth_ratio": "Charge-transfer resistance growth vs new",
    "ch_temp_max_c": "Peak charging temperature",
    "ch_temp_rise_c": "Temperature rise during charge",
    "ch_temp_mean_c": "Mean charging temperature",
    "ch_thermal_dose_c_h": "Thermal dose this cycle",
    "ch_frac_above_warn": "Time above temperature warning limit",
    "ambient_temp_c": "Ambient temperature",
    "cycle_index": "Cycle count",
    "equivalent_full_cycles": "Equivalent full cycles (throughput)",
    "calendar_age_days": "Calendar age",
    "mean_rest_h": "Average rest between cycles",
    "cum_thermal_dose_c_h": "Cumulative thermal dose",
}


# Simple explanations of what each feature group means.
GROUP_DESCRIPTIONS: Dict[str, str] = {
    "charge_acceptance": (
        "How much charge the battery accepts during charging. "
        "As the battery ages, this behaviour changes."
    ),

    "internal_resistance": (
        "Changes in the battery's internal resistance. "
        "Higher resistance usually means more heat and lower usable power."
    ),

    "thermal_stress": (
        "How much heat the battery experiences during charging. "
        "High temperatures can speed up battery ageing."
    ),

    "usage_history": (
        "How much the battery has been used and how old it is. "
        "More cycles and more ageing usually lead to more degradation."
    ),
}


# ===========================================================================
# Basic functions for calculating features from one battery phase
# ===========================================================================


def _integrate_ah(
    time_s: np.ndarray,
    current_a: np.ndarray
) -> float:
    """Calculate amp-hours from current and time."""

    if len(time_s) < 2:
        return 0.0

    # Integrate current over time and convert seconds to hours.
    return float(
        np.trapezoid(
            np.abs(current_a),
            time_s
        ) / 3600.0
    )


def _split_cc_cv(
    phase: PhaseTelemetry,
    fmt: BatteryFormat
) -> tuple[np.ndarray, np.ndarray]:
    """Separate a charge into CC and CV parts."""

    current = phase.current_a
    voltage = phase.voltage_v

    # Ignore very small current values.
    charging = current > 0.02 * fmt.rated_capacity_ah

    if charging.sum() < 5:
        return (
            np.zeros_like(charging),
            np.zeros_like(charging)
        )

    # Find the normal charging current.
    # 90th percentile is used so one abnormal spike doesn't affect it.
    i_plateau = float(
        np.percentile(current[charging], 90)
    )

    if i_plateau <= 0:
        return (
            np.zeros_like(charging),
            np.zeros_like(charging)
        )

    # CC means current is still close to the normal charging current.
    cc_mask = charging & (
        current > 0.90 * i_plateau
    )

    # CV starts after CC ends and the voltage is close to the maximum.
    cv_mask = np.zeros_like(charging)

    if cc_mask.any():
        last_cc = int(
            np.flatnonzero(cc_mask)[-1]
        )

        after = np.zeros_like(charging)
        after[last_cc + 1:] = True

        cv_mask = (
            after
            & charging
            & (voltage > 0.97 * fmt.v_max)
        )

    return cc_mask, cv_mask


def _estimate_ohmic_resistance(
    phase: PhaseTelemetry,
    fmt: BatteryFormat
) -> Optional[float]:
    """Estimate internal resistance from the start of charging."""

    current = phase.current_a
    voltage = phase.voltage_v

    # Look for the point where the charger turns on.
    threshold = 0.1 * fmt.rated_capacity_ah

    on = np.flatnonzero(
        current > threshold
    )

    if on.size == 0 or on[0] == 0:
        return None

    i_after = int(on[0])
    i_before = i_after - 1

    # Measure the change in current and voltage.
    delta_i = (
        current[i_after] -
        current[i_before]
    )

    delta_v = (
        voltage[i_after] -
        voltage[i_before]
    )

    # Not a strong enough current change.
    if delta_i <= threshold * 0.5:
        return None

    # R = change in voltage / change in current.
    resistance = delta_v / delta_i

    # Ignore values that are not realistic.
    if not (
        0.0 <
        resistance <
        5.0 / fmt.rated_capacity_ah
    ):
        return None

    return float(resistance)


def _normalise_resistance(
    resistance_ohm: float,
    fmt: BatteryFormat
) -> float:
    """Convert resistance into a value that can be compared across batteries."""

    # Calculate the voltage range of the battery.
    window = max(
        fmt.v_max - fmt.v_min,
        1e-6
    )

    # Scale resistance using battery capacity and voltage range.
    return (
        resistance_ohm *
        fmt.rated_capacity_ah /
        window
    )


def _thermal_dose(
    phase: PhaseTelemetry,
    baseline_c: float = 25.0
) -> float:
    """Calculate how much time-temperature exposure the battery had."""

    if len(phase.time_s) < 2:
        return 0.0

    # Only count temperature above the baseline.
    excess = np.maximum(
        0.0,
        phase.temperature_c - baseline_c
    )

    # Integrate the temperature exposure over time.
    return float(
        np.trapezoid(
            excess,
            phase.time_s
        ) / 3600.0
    )


# ===========================================================================
# Calculate features for one cycle
# ===========================================================================


def _charge_features(
    record: CycleRecord,
    fmt: BatteryFormat
) -> Dict[str, float]:
    """Calculate features from the charging phase."""

    nan = float("nan")

    # Default values if charge data is missing.
    blank = {
        "cc_capacity_frac": nan,
        "cv_capacity_frac": nan,
        "cc_cv_ah_ratio": nan,
        "cc_time_fraction": nan,
        "total_charge_frac": nan,
        "charge_time_1c_equiv": nan,
        "mean_charge_c_rate": nan,
        "dvdt_cc_per_frac": nan,
        "v_norm_at_cc_end": nan,
        "ohmic_r_norm": nan,
    }

    phase = record.charge

    if phase is None:
        return blank

    time_s = phase.time_s
    current = phase.current_a
    voltage = phase.voltage_v

    # Find the CC and CV sections.
    cc_mask, cv_mask = _split_cc_cv(
        phase,
        fmt
    )

    if cc_mask.sum() < 3:
        return blank

    # Calculate how much charge was added in each phase.
    cc_ah = _integrate_ah(
        time_s[cc_mask],
        current[cc_mask]
    )

    cv_ah = (
        _integrate_ah(
            time_s[cv_mask],
            current[cv_mask]
        )
        if cv_mask.sum() >= 3
        else 0.0
    )

    total_ah = cc_ah + cv_ah

    # Calculate time spent in each phase.
    cc_time = float(
        time_s[cc_mask][-1] -
        time_s[cc_mask][0]
    )

    cv_time = (
        float(
            time_s[cv_mask][-1] -
            time_s[cv_mask][0]
        )
        if cv_mask.sum() >= 3
        else 0.0
    )

    total_time = cc_time + cv_time

    # Calculate average charging C-rate.
    charging = (
        current >
        0.02 * fmt.rated_capacity_ah
    )

    mean_c_rate = (
        float(
            fmt.to_c_rate(
                np.mean(current[charging])
            )
        )
        if charging.any()
        else nan
    )

    # Look at how quickly the voltage rises during CC charging.
    cc_v_norm = fmt.to_v_norm(
        voltage[cc_mask]
    )

    delta_v_norm = float(
        cc_v_norm[-1] -
        cc_v_norm[0]
    )

    cc_frac = (
        cc_ah /
        fmt.rated_capacity_ah
    )

    dvdt_cc_per_frac = (
        delta_v_norm /
        (cc_frac + EPS)
    )

    return {
        "cc_capacity_frac": cc_frac,

        "cv_capacity_frac":
            cv_ah /
            fmt.rated_capacity_ah,

        "cc_cv_ah_ratio":
            cc_ah /
            (cv_ah + EPS),

        "cc_time_fraction":
            cc_time /
            (total_time + EPS),

        "total_charge_frac":
            total_ah /
            fmt.rated_capacity_ah,

        # Express charge duration in a normalized way.
        "charge_time_1c_equiv":
            (total_time / 3600.0) *
            (
                mean_c_rate
                if np.isfinite(mean_c_rate)
                else 1.0
            ),

        "mean_charge_c_rate":
            mean_c_rate,

        "dvdt_cc_per_frac":
            dvdt_cc_per_frac,

        "v_norm_at_cc_end":
            float(cc_v_norm[-1]),

        "ohmic_r_norm": (
            _normalise_resistance(r, fmt)
            if (
                r :=
                _estimate_ohmic_resistance(
                    phase,
                    fmt
                )
            ) is not None
            else nan
                ),
    }


def _thermal_features(
    record: CycleRecord,
    fmt: BatteryFormat
) -> Dict[str, float]:

    nan = float("nan")
    phase = record.charge

    # If there is no charge data, return empty thermal features.
    if phase is None:
        return {
            "ch_temp_max_c": nan,
            "ch_temp_rise_c": nan,
            "ch_temp_mean_c": nan,
            "ch_thermal_dose_c_h": nan,
            "ch_frac_above_warn": nan,
            "ambient_temp_c":
                record.ambient_temp_c,
        }

    temp = phase.temperature_c

    return {
        "ch_temp_max_c":
            float(np.nanmax(temp)),

        "ch_temp_rise_c":
            float(
                np.nanmax(temp) -
                temp[0]
            ),

        "ch_temp_mean_c":
            float(np.nanmean(temp)),

        "ch_thermal_dose_c_h":
            _thermal_dose(phase),

        "ch_frac_above_warn":
            float(
                np.mean(
                    temp >
                    fmt.temp_warn_c
                )
            ),

        "ambient_temp_c":
            record.ambient_temp_c,
    }


def _impedance_features(
    record: CycleRecord,
    fmt: BatteryFormat
) -> Dict[str, float]:
    """Create features from impedance measurements."""

    nan = float("nan")

    # No impedance data available.
    if record.impedance is None:
        return {
            "re_norm": nan,
            "rct_norm": nan,
            "re_growth_ratio": nan,
            "rct_growth_ratio": nan,
        }

    return {
        "re_norm":
            _normalise_resistance(
                record.impedance.re_ohm,
                fmt
            ),

        "rct_norm":
            _normalise_resistance(
                record.impedance.rct_ohm,
                fmt
            ),

        # These are calculated later using battery history.
        "re_growth_ratio": nan,
        "rct_growth_ratio": nan,
    }


def _audit_features(
    record: CycleRecord,
    fmt: BatteryFormat
) -> Dict[str, float]:
    """Create features from the discharge for reference only."""

    nan = float("nan")

    out = {
        "audit_capacity_ah":
            record.measured_capacity_ah
            or nan,

        "audit_dis_temp_max_c": nan,
        "audit_dis_temp_rise_c": nan,
        "audit_min_voltage_v": nan,
        "audit_min_v_norm": nan,
        "audit_dis_duration_h": nan,
        "audit_mean_dis_c_rate": nan,
        "audit_energy_wh": nan,
        "audit_dis_thermal_dose_c_h": nan,
    }

    phase = record.discharge

    if phase is None:
        return out

    time_s = phase.time_s
    current = phase.current_a
    voltage = phase.voltage_v
    temp = phase.temperature_c

    # Negative current means the battery is discharging.
    discharging = (
        current <
        -0.02 * fmt.rated_capacity_ah
    )

    out["audit_dis_temp_max_c"] = float(
        np.nanmax(temp)
    )

    out["audit_dis_temp_rise_c"] = float(
        np.nanmax(temp) -
        temp[0]
    )

    out["audit_min_voltage_v"] = float(
        np.nanmin(voltage)
    )

    out["audit_min_v_norm"] = float(
        fmt.to_v_norm(
            np.nanmin(voltage)
        )
    )

    out["audit_dis_duration_h"] = (
        phase.duration_s / 3600.0
    )

    out["audit_dis_thermal_dose_c_h"] = (
        _thermal_dose(phase)
    )

    if discharging.any():

        out["audit_mean_dis_c_rate"] = float(
            abs(
                fmt.to_c_rate(
                    np.mean(
                        current[discharging]
                    )
                )
            )
        )

        out["audit_energy_wh"] = float(
            np.trapezoid(
                np.abs(
                    current[discharging] *
                    voltage[discharging]
                ),
                time_s[discharging]
            ) / 3600.0
        )

    return out


# ===========================================================================
# Build the final dataset
# ===========================================================================


def build_feature_table(
    records: List[CycleRecord]
) -> pd.DataFrame:
    """Convert all CycleRecords into a table for the ML model."""

    if not records:
        raise ValueError(
            "No cycle records supplied"
        )

    rows = []

    # Process every battery cycle.
    for record in records:

        # Get the specifications of this battery.
        fmt = get_format(
            record.format_key
        )

        # Create the basic row.
        row: Dict[str, object] = {
            "battery_id":
                record.battery_id,

            "format_key":
                record.format_key,

            "cycle_index":
                record.cycle_index,

            "timestamp":
                record.timestamp,

            "rated_capacity_ah":
                fmt.rated_capacity_ah,
        }

        # Add all the different feature groups.
        row.update(
            _charge_features(
                record,
                fmt
            )
        )

        row.update(
            _thermal_features(
                record,
                fmt
            )
        )

        row.update(
            _impedance_features(
                record,
                fmt
            )
        )

        row.update(
            _audit_features(
                record,
                fmt
            )
        )

        rows.append(row)

    # Convert all rows into a dataframe.
    df = pd.DataFrame(rows)

    df = (
        df.sort_values(
            ["battery_id", "cycle_index"]
        )
        .reset_index(drop=True)
    )

    # Calculate SOH from measured capacity and rated capacity.
    df["soh"] = (
        df["audit_capacity_ah"] /
        df["rated_capacity_ah"]
    )

    # Calculate features that need battery history.
    per_battery = []

    for battery_id, group in df.groupby(
        "battery_id",
        sort=False
    ):

        group = (
            group
            .sort_values("cycle_index")
            .copy()
        )

        # Count equivalent full cycles.
        # Only use previous cycles so we do not leak the current label.
        throughput = (
            group["audit_capacity_ah"]
            .fillna(0.0)
            .cumsum()
            .shift(1)
            .fillna(0.0)
        )

        group["equivalent_full_cycles"] = (
            throughput /
            group["rated_capacity_ah"]
        )

        # Calculate how many days have passed since the first cycle.
        t0 = group["timestamp"].iloc[0]

        group["calendar_age_days"] = (
            group["timestamp"] - t0
        ).dt.total_seconds() / 86400.0

        # Calculate the time between cycles.
        gaps_h = (
            group["timestamp"]
            .diff()
            .dt.total_seconds() / 3600.0
        )

        group["mean_rest_h"] = (
            gaps_h
            .expanding()
            .mean()
            .fillna(0.0)
        )

        # Calculate total thermal exposure from previous cycles.
        group["cum_thermal_dose_c_h"] = (
            group["ch_thermal_dose_c_h"]
            .fillna(0.0)
            .cumsum()
            .shift(1)
            .fillna(0.0)
        )

        # Calculate resistance growth compared with the battery's
        # early healthy state.
        for src, dst in (
            ("re_norm", "re_growth_ratio"),
            ("rct_norm", "rct_growth_ratio")
        ):

            valid = group[src].dropna()

            if len(valid) >= 3:

                # Use the first few readings as the baseline.
                baseline = float(
                    valid.iloc[:5].median()
                )

                group[dst] = (
                    group[src] /
                    (baseline + EPS)
                )

            else:
                group[dst] = np.nan

        per_battery.append(group)

    # Combine all batteries again.
    df = pd.concat(
        per_battery,
        ignore_index=True
    )

    # Impedance tests are only done sometimes.
    # Carry the latest available value forward.
    eis_cols = [
        "re_norm",
        "rct_norm",
        "re_growth_ratio",
        "rct_growth_ratio"
    ]

    df[eis_cols] = (
        df.groupby("battery_id")[eis_cols]
        .ffill()
    )

    logger.info(
        "Built feature table: %d cycles, %d batteries, %d model features",
        len(df),
        df["battery_id"].nunique(),
        len(SOH_FEATURES),
    )

    return df


def assert_no_leakage(
    feature_names: List[str]
) -> None:
    """Check that discharge-based data is not used by the SOH model."""

    # These values come from the full discharge and would give the model
    # information about the answer it is trying to predict.
    leaked = [
        f
        for f in feature_names
        if f.startswith("audit_")
        or f in (
            "soh",
            "audit_capacity_ah"
        )
    ]

    if leaked:
        raise ValueError(
            "Target leakage detected. These columns are derived from the full "
            f"discharge and must never be model inputs: {leaked}. "
            "See the design rule in backend/batris/features.py."
        )

    # Also make sure every selected feature is officially allowed.
    unknown = [
        f
        for f in feature_names
        if f not in SOH_FEATURES
    ]

    if unknown:
        raise ValueError(
            f"Features not declared in SOH_FEATURES: {unknown}"
        )


def feature_group_of(
    feature: str
) -> str:
    """Find which degradation group a feature belongs to."""

    for group, members in FEATURE_GROUPS.items():

        if feature in members:
            return group

    return "other"
