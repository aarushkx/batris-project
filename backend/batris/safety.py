"""
Safety checks, charging recommendations and second-life grading.

This module uses rule-based decisions instead of ML because safety decisions
need clear explanations. Each recommendation is based on known limits and
measured battery values.

The dataset does not contain real safety failures, so a safety model cannot be
trained reliably. Machine learning is used for battery state estimation, while
this module converts those results into clear actions using fixed rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .formats import BatteryFormat
from .models.anomaly import AnomalyResult

# Risk bands. Boundaries are on a 0-100 scale.
RISK_BANDS = [
    (0, 20, "LOW", "Normal operation. No restrictions."),
    (20, 45, "MODERATE", "Serviceable with monitoring."),
    (45, 70, "ELEVATED", "Operate with derating and increased inspection."),
    (70, 101, "HIGH", "Withdraw from demanding service pending inspection."),
]


@dataclass
class Recommendation:
    """One actionable instruction."""

    category: str       # charging | thermal | usage | inspection | disposition
    priority: str       # routine | advised | urgent
    action: str
    rationale: str

    def as_dict(self) -> Dict:
        return {
            "category": self.category,
            "priority": self.priority,
            "action": self.action,
            "rationale": self.rationale,
        }


@dataclass
class SafetyAssessment:
    """Complete safety picture for a battery at a point in time."""

    risk_score: float
    risk_band: str
    band_meaning: str
    drivers: List[Dict] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    charging_envelope: Dict = field(default_factory=dict)

    def as_dict(self) -> Dict:
        return {
            "risk_score": round(self.risk_score, 1),
            "risk_band": self.risk_band,
            "band_meaning": self.band_meaning,
            "risk_drivers": self.drivers,
            "safe_charging_envelope": self.charging_envelope,
            "recommendations": [r.as_dict() for r in self.recommendations],
        }


# ===========================================================================
# Risk scoring
# ===========================================================================

def _health_risk(soh: float, fmt: BatteryFormat) -> tuple[float, str]:
    """Calculates risk based only on battery capacity loss.

    The risk increases when the battery approaches end-of-life because large
    differences between cells can affect pack performance and safety.
    """
    if soh >= fmt.eol_soh:
        return 0.0, f"SOH {100 * soh:.1f}% is above the {100 * fmt.eol_soh:.0f}% end-of-life threshold."
    if soh >= fmt.second_life_floor_soh:
        span = fmt.eol_soh - fmt.second_life_floor_soh
        risk = 35.0 * (fmt.eol_soh - soh) / max(span, 1e-6)
        return risk, (
            f"SOH {100 * soh:.1f}% is below the {100 * fmt.eol_soh:.0f}% first-life "
            "threshold but still within the second-life range."
        )
    deficit = fmt.second_life_floor_soh - soh
    return min(70.0, 35.0 + 200.0 * deficit), (
        f"SOH {100 * soh:.1f}% is below the {100 * fmt.second_life_floor_soh:.0f}% "
        "second-life floor; internal degradation is advanced."
    )


def _resistance_risk(rct_growth: Optional[float]) -> tuple[float, str]:
    """Calculates risk based on increase in internal resistance.

    High resistance causes more heat generation during operation and can create
    hot spots in battery packs.
    """
    if rct_growth is None or not np.isfinite(rct_growth):
        return 0.0, ""
    if rct_growth < 1.3:
        return 0.0, ""
    risk = min(45.0, 60.0 * (rct_growth - 1.3))
    return risk, (
        f"Charge-transfer resistance has grown to {rct_growth:.2f}x baseline, "
        "increasing self-heating under load."
    )


def _thermal_risk(peak_temp: Optional[float], fmt: BatteryFormat) -> tuple[float, str]:
    if peak_temp is None or not np.isfinite(peak_temp):
        return 0.0, ""
    if peak_temp < fmt.temp_warn_c - 5:
        return 0.0, ""
    if peak_temp < fmt.temp_warn_c:
        return 8.0, f"Peak temperature {peak_temp:.1f} C is approaching the {fmt.temp_warn_c:.0f} C advisory limit."
    span = max(fmt.temp_critical_c - fmt.temp_warn_c, 1e-6)
    risk = 25.0 + 50.0 * min(1.0, (peak_temp - fmt.temp_warn_c) / span)
    return risk, f"Peak temperature {peak_temp:.1f} C exceeded the {fmt.temp_warn_c:.0f} C advisory limit."


def _degradation_rate_risk(recent_slope_per_cycle: Optional[float]) -> tuple[float, str]:
    """Calculates risk based on the battery's ageing speed.

    A rapidly increasing capacity loss rate can indicate the battery is entering
    a failure stage where degradation becomes faster and less predictable.
    """
    if recent_slope_per_cycle is None or not np.isfinite(recent_slope_per_cycle):
        return 0.0, ""
    fade_per_100 = -100.0 * recent_slope_per_cycle  # positive when losing health
    if fade_per_100 < 3.0:
        return 0.0, ""
    risk = min(40.0, 8.0 * (fade_per_100 - 3.0))
    return risk, (
        f"Capacity is currently fading at about {fade_per_100:.1f} SOH points per "
        "100 cycles, faster than the linear-ageing regime."
    )


def assess_safety(
    soh: float,
    fmt: BatteryFormat,
    anomaly: Optional[AnomalyResult] = None,
    rct_growth: Optional[float] = None,
    peak_temp_c: Optional[float] = None,
    fade_slope_per_cycle: Optional[float] = None,
    soh_uncertainty: Optional[float] = None,
) -> SafetyAssessment:
    """Combine health, resistance, thermal, fade-rate and anomaly evidence."""

    components: List[tuple[str, float, str]] = []

    risk, note = _health_risk(soh, fmt)
    components.append(("capacity_loss", risk, note))

    risk, note = _resistance_risk(rct_growth)
    if note:
        components.append(("resistance_growth", risk, note))

    risk, note = _thermal_risk(peak_temp_c, fmt)
    if note:
        components.append(("thermal_exposure", risk, note))

    risk, note = _degradation_rate_risk(fade_slope_per_cycle)
    if note:
        components.append(("fade_acceleration", risk, note))

    if anomaly is not None and anomaly.anomalies:
        severity_weight = {"info": 5.0, "warning": 30.0, "critical": 65.0}
        worst = max(severity_weight[a.severity] for a in anomaly.anomalies)
        codes = ", ".join(sorted({a.code for a in anomaly.anomalies}))
        components.append((
            "detected_anomalies", worst,
            f"Active anomaly detections: {codes}.",
        ))

   # Combines different risk factors into one score.
    # Critical issues get higher priority, while multiple smaller issues can still
    # slightly increase the final risk score.
    scores = [c[1] for c in components] or [0.0]
    primary = max(scores)
    secondary = sum(sorted(scores, reverse=True)[1:])
    total = float(np.clip(primary + 0.25 * secondary, 0.0, 100.0))

    # A larger prediction range means the model is less certain.
    # Uncertainty in safety-related predictions increases the risk score.
    if soh_uncertainty is not None and np.isfinite(soh_uncertainty) and soh_uncertainty > 0.08:
        total = float(np.clip(total + 5.0, 0.0, 100.0))
        components.append((
            "estimate_uncertainty", 5.0,
            f"SOH estimate carries a wide {100 * soh_uncertainty:.1f} point "
            "confidence interval; assessment is conservative as a result.",
        ))

    band, meaning = "LOW", RISK_BANDS[0][3]
    for low, high, name, description in RISK_BANDS:
        if low <= total < high:
            band, meaning = name, description
            break

    drivers = [
        {"factor": name, "contribution": round(value, 1), "finding": note}
        for name, value, note in sorted(components, key=lambda c: c[1], reverse=True)
        if note
    ]

    assessment = SafetyAssessment(
        risk_score=total, risk_band=band, band_meaning=meaning, drivers=drivers,
    )
    assessment.charging_envelope = safe_charging_envelope(
        soh, fmt, total, peak_temp_c)
    assessment.recommendations = build_recommendations(
        soh, fmt, assessment, anomaly, rct_growth, peak_temp_c, fade_slope_per_cycle
    )
    return assessment


# ===========================================================================
# Safe charging practice
# ===========================================================================

def safe_charging_envelope(
    soh: float, fmt: BatteryFormat, risk_score: float,
    peak_temp_c: Optional[float] = None,
) -> Dict:
    """Creates charging limits based on the battery format and condition.

    Returns practical values that can be used by the charger.
    Older or degraded batteries need lower charging limits to reduce heat and
    damage risk.
    """
    # Current derating tracks remaining health, floored so the pack stays usable.
    if soh >= fmt.eol_soh:
        current_factor = 1.0
    elif soh >= fmt.second_life_floor_soh:
        current_factor = 0.75
    else:
        current_factor = 0.5

    if risk_score >= 70:
        current_factor = min(current_factor, 0.35)
    elif risk_score >= 45:
        current_factor = min(current_factor, 0.6)

    max_c_rate = round(fmt.max_charge_c_rate * current_factor, 3)

    # Defines the safe state-of-charge range for charging.
    # Keeping batteries away from high SOC reduces ageing, so the allowed range
    # becomes smaller as the battery gets older.
    if soh >= fmt.eol_soh and risk_score < 45:
        soc_window = (10, 90)
        soc_note = "Charge to 90% for daily use; reserve 100% for long trips."
    elif soh >= fmt.second_life_floor_soh:
        soc_window = (20, 85)
        soc_note = "Keep within 20-85% to slow further capacity loss."
    else:
        soc_window = (25, 80)
        soc_note = "Restrict to 25-80%; the cell has limited margin at both extremes."

    # Sets the charging voltage limit for partial charging.
    #
    # The voltage limit helps control the maximum SOC reached by the battery.
    # Voltage and SOC are not linearly related, so the upper limit is calculated
    # carefully instead of using a simple voltage conversion.
    #
    # Only the upper charging limit is adjusted. The lower SOC limit is handled by
    # the BMS using its SOC estimation.
    upper_fraction = soc_window[1] / 100.0
    if upper_fraction > 0.5:
        span = (upper_fraction - 0.5) / 0.5
        charge_voltage_setpoint = round(
            fmt.nominal_voltage_v +
            (fmt.v_max - fmt.nominal_voltage_v) * span, 2
        )
    else:
        charge_voltage_setpoint = None

    return {
        "max_charge_c_rate": max_c_rate,
        "max_charge_current_a": round(max_c_rate * fmt.rated_capacity_ah, 2),
        "derating_applied": round(1.0 - current_factor, 2),
        "recommended_soc_window_percent": list(soc_window),
        "charge_voltage_setpoint_v": charge_voltage_setpoint,
        "charge_voltage_setpoint_note": (
            "Approximate constant-voltage termination setpoint for the recommended "
            "SOC ceiling. The lower SOC bound should be enforced from the BMS "
            "state-of-charge estimate, not from a voltage threshold: the "
            "open-circuit-voltage curve is too flat in that region for voltage to "
            "identify state of charge reliably."
        ),
        "soc_guidance": soc_note,
        "charge_temperature_window_c": [fmt.temp_min_charge_c, fmt.temp_max_charge_c],
        "absolute_limits": {
            "v_max": fmt.v_max,
            "v_min_recommended": fmt.v_min,
            "v_min_absolute": fmt.v_min_absolute,
            "temp_critical_c": fmt.temp_critical_c,
        },
    }


def build_recommendations(
    soh: float,
    fmt: BatteryFormat,
    assessment: SafetyAssessment,
    anomaly: Optional[AnomalyResult],
    rct_growth: Optional[float],
    peak_temp_c: Optional[float],
    fade_slope_per_cycle: Optional[float],
) -> List[Recommendation]:
    """Translate the assessment into prioritised, specific actions."""
    recs: List[Recommendation] = []
    envelope = assessment.charging_envelope

    # -- charging ------------------------------------------------------------
    recs.append(Recommendation(
        "charging", "routine",
        f"Limit charge current to {envelope['max_charge_current_a']} A "
        f"({envelope['max_charge_c_rate']}C) and keep the pack within "
        f"{envelope['recommended_soc_window_percent'][0]}-"
        f"{envelope['recommended_soc_window_percent'][1]}% state of charge.",
        envelope["soc_guidance"],
    ))

    if envelope["derating_applied"] > 0:
        recs.append(Recommendation(
            "charging", "advised",
            f"Apply a {100 * envelope['derating_applied']:.0f}% reduction to the "
            "nameplate charge rate.",
            "A degraded cell has less active material available to accept the "
            "same current, so the original rate now produces more lithium "
            "plating and more heat than it did when new.",
        ))

    recs.append(Recommendation(
        "charging", "routine",
        f"Do not charge below {fmt.temp_min_charge_c:.0f} C or above "
        f"{fmt.temp_max_charge_c:.0f} C cell temperature.",
        "Charging a cold cell plates metallic lithium irreversibly; charging a "
        "hot one accelerates electrolyte breakdown and gas generation.",
    ))

    if soh < fmt.eol_soh:
        recs.append(Recommendation(
            "charging", "advised",
            "Avoid DC fast charging except when operationally necessary.",
            "High-rate charging concentrates stress at exactly the electrode "
            "sites already depleted in an aged cell.",
        ))

    # -- thermal -------------------------------------------------------------
    if peak_temp_c is not None and np.isfinite(peak_temp_c) and peak_temp_c >= fmt.temp_warn_c - 5:
        recs.append(Recommendation(
            "thermal", "advised" if peak_temp_c < fmt.temp_warn_c else "urgent",
            f"Investigate cooling performance; peak temperature reached "
            f"{peak_temp_c:.1f} C against a {fmt.temp_warn_c:.0f} C advisory limit.",
            "Degradation rate roughly doubles for every 10 C rise, so thermal "
            "management pays back faster than any other intervention.",
        ))

    # -- resistance ----------------------------------------------------------
    if rct_growth is not None and np.isfinite(rct_growth) and rct_growth >= 1.5:
        recs.append(Recommendation(
            "inspection", "urgent" if rct_growth >= 2.0 else "advised",
            "Inspect cell interconnects, busbar torque and terminal corrosion.",
            f"Resistance at {rct_growth:.2f}x baseline is often a joint or "
            "contact problem rather than cell chemistry, and that is repairable.",
        ))

    # -- fade acceleration ---------------------------------------------------
    if fade_slope_per_cycle is not None and np.isfinite(fade_slope_per_cycle):
        fade_per_100 = -100.0 * fade_slope_per_cycle
        if fade_per_100 >= 3.0:
            recs.append(Recommendation(
                "usage", "urgent",
                "Reduce depth of discharge and shorten the inspection interval; "
                "this pack appears to have passed the ageing knee.",
                f"Fade has accelerated to roughly {fade_per_100:.1f} SOH points "
                "per 100 cycles. Post-knee degradation is associated with "
                "lithium plating, which also raises internal short risk.",
            ))

    # -- anomalies -----------------------------------------------------------
    if anomaly is not None:
        for item in anomaly.anomalies:
            if item.severity == "critical":
                recs.append(Recommendation(
                    "inspection", "urgent",
                    f"Investigate {item.code} before returning the pack to service.",
                    item.detail,
                ))

    # -- inspection cadence and disposition ----------------------------------
    cadence = {
        "LOW": "Standard interval (every 6 months or 200 cycles).",
        "MODERATE": "Every 3 months or 100 cycles.",
        "ELEVATED": "Monthly, with temperature and resistance trending.",
        "HIGH": "Immediate inspection; do not defer.",
    }[assessment.risk_band]
    recs.append(Recommendation("inspection", "routine", cadence,
                               f"Cadence set by the {assessment.risk_band} risk band."))

    if assessment.risk_band == "HIGH":
        recs.append(Recommendation(
            "disposition", "urgent",
            "Withdraw from demanding duty. Do not deploy in passenger-carrying "
            "or unattended applications until inspected.",
            assessment.band_meaning,
        ))

    return recs


# ===========================================================================
# Second-life grading
# ===========================================================================

SECOND_LIFE_GRADES = {
    "A": "Suitable for continued first-life automotive use.",
    "B": "Suitable for second-life stationary storage (solar buffering, backup).",
    "C": "Suitable only for low-power, derated, attended applications.",
    "RECYCLE": "Not suitable for reuse. Route to material recovery.",
}


def _grade_for_soh(soh: float, fmt: BatteryFormat) -> str:
    """Map a SOH value to a reuse grade."""
    if soh >= fmt.eol_soh:
        return "A"
    if soh >= 0.70:
        return "B"
    if soh >= fmt.second_life_floor_soh:
        return "C"
    return "RECYCLE"


def grade_second_life(
    soh: float,
    fmt: BatteryFormat,
    assessment: SafetyAssessment,
    soh_lower: Optional[float] = None,
    soh_upper: Optional[float] = None,
) -> Dict:
    """Assigns a second-life grade and shows how reliable the result is.

    The grade is based on the estimated battery health, while the confidence
    interval shows how much the result should be trusted.

    If the confidence range crosses grade limits, more testing is recommended.
    Safety risk always has priority over capacity, so high-risk batteries are not
    recommended for reuse.
    """
    grade = _grade_for_soh(soh, fmt)
    safety_override = assessment.risk_band == "HIGH"
    if safety_override:
        grade = "RECYCLE"
        reason = (
            "Safety risk band is HIGH. Reuse is not recommended irrespective of "
            f"remaining capacity ({100 * soh:.1f}% SOH)."
        )
    elif grade == "A":
        reason = (
            f"Estimated SOH {100 * soh:.1f}% is at or above the "
            f"{100 * fmt.eol_soh:.0f}% first-life threshold."
        )
    elif grade == "B":
        reason = (
            f"Estimated SOH {100 * soh:.1f}% is below the first-life threshold but "
            "retains ample capacity for stationary duty, where energy density "
            "matters far less than in a vehicle."
        )
    elif grade == "C":
        reason = (
            f"Estimated SOH {100 * soh:.1f}% is close to the "
            f"{100 * fmt.second_life_floor_soh:.0f}% reuse floor. Only derated, "
            "attended applications are appropriate."
        )
    else:
        reason = (
            f"Estimated SOH {100 * soh:.1f}% is below the "
            f"{100 * fmt.second_life_floor_soh:.0f}% reuse floor. Material "
            "recovery yields more value than reuse."
        )

    # -- how much to trust this grade ---------------------------------------
    interval_width = None
    worst_case_grade = grade
    best_case_grade = grade
    if soh_lower is not None and soh_upper is not None and np.isfinite(soh_lower):
        interval_width = float(soh_upper - soh_lower)
        worst_case_grade = "RECYCLE" if safety_override else _grade_for_soh(
            soh_lower, fmt)
        best_case_grade = "RECYCLE" if safety_override else _grade_for_soh(
            soh_upper, fmt)

    if interval_width is None:
        confidence = "UNKNOWN"
    elif interval_width <= 0.05:
        confidence = "HIGH"
    elif interval_width <= 0.12:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    ambiguous = worst_case_grade != best_case_grade

    if safety_override:
        action = (
            "Safety-driven disposition. Certified testing will not change this "
            "outcome while the risk band remains HIGH."
        )
    elif ambiguous or confidence == "LOW":
        action = (
            f"The confidence interval spans grades {worst_case_grade} to "
            f"{best_case_grade}. This estimate is not precise enough to support a "
            "binding resale, warranty or disposal decision. Commission a "
            "certified capacity test before committing."
        )
    else:
        action = (
            "Estimate is precise enough for triage and routing. A certified "
            "capacity test is still required before any warranted resale."
        )

    return {
        "grade": grade,
        "recommendation": SECOND_LIFE_GRADES[grade],
        "rationale": reason,
        "grading_basis": "point estimate of SOH",
        "grading_basis_soh": round(float(soh), 4),
        "grade_confidence": confidence,
        "grade_is_ambiguous": bool(ambiguous),
        "worst_case_grade": worst_case_grade,
        "best_case_grade": best_case_grade,
        "confidence_interval_width_soh_points": (
            round(100 * interval_width, 1) if interval_width is not None else None
        ),
        "next_step": action,
        "safety_override_applied": bool(safety_override),
        "estimated_remaining_energy_wh": round(soh * fmt.rated_energy_wh, 1),
    }
