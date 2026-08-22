"""
Assesses a battery without previous history.

This handles the second-life case where a battery has no cycle records or
baseline data.

Main considerations:
1. NO HISTORY
   Some features need previous cycles for comparison. If history is missing,
   those checks are marked unavailable instead of making false assumptions.

2. VARYING INPUT QUALITY
   The model used depends on the information provided by the user. Each tier
   has its own measured accuracy.

3. CHEMISTRY DIFFERENCES
   Models are trained on LCO cells, so other chemistries may require
   extrapolation. The system reports this uncertainty instead of hiding it.
"""

from __future__ import annotations

from .paths import MODELS_DIR

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .explain import EXPLANATION_CAVEAT, explain_prediction, summarise_factors
from .formats import get_format
from .models.anomaly import AnomalyDetector
from .models.soh import SOHModel
from .onboard import direct_measurement
from .safety import assess_safety, grade_second_life
from .tiers import InputTier, get_tier

logger = logging.getLogger(__name__)

# Chemistries represented in the training data.
TRAINED_CHEMISTRIES = {"LCO"}

# Expands the uncertainty range when the battery chemistry was not included
# in the training data.
# This is an engineering assumption and is clearly mentioned in the output.
CROSS_CHEMISTRY_INTERVAL_FACTOR = 1.6


def chemistry_transfer_note(format_key: str) -> Dict:
    """Checks how different the battery format is from the training data."""
    fmt = get_format(format_key)
    in_distribution = fmt.chemistry in TRAINED_CHEMISTRIES

    if in_distribution:
        return {
            "in_distribution": True,
            "interval_factor": 1.0,
            "trained_chemistries": sorted(TRAINED_CHEMISTRIES),
            "requested_chemistry": fmt.chemistry,
            "note": (
                f"The models were trained on {fmt.chemistry} cells, so this "
                "assessment is within the validated distribution."
            ),
        }

    return {
        "in_distribution": False,
        "interval_factor": CROSS_CHEMISTRY_INTERVAL_FACTOR,
        "trained_chemistries": sorted(TRAINED_CHEMISTRIES),
        "requested_chemistry": fmt.chemistry,
        "note": (
            f"EXTRAPOLATION WARNING. The models were trained only on "
            f"{'/'.join(sorted(TRAINED_CHEMISTRIES))} cells and this battery is "
            f"{fmt.chemistry}. The platform normalises telemetry so the numbers "
            f"are dimensionally comparable across formats, but that does not make "
            f"the degradation physics comparable. {fmt.chemistry} cells age and "
            f"charge differently. The confidence interval has been widened by "
            f"{CROSS_CHEMISTRY_INTERVAL_FACTOR}x to reflect this, but that factor "
            f"is an engineering judgement, not a measured quantity -- validating "
            f"it would require {fmt.chemistry} cycling data, which this project "
            f"does not have. Treat the result as indicative and commission a "
            f"certified capacity test before acting on it."
        ),
    }


class UnseenBatteryAssessor:
    """Assess a battery supplied by a user, with no prior record."""

    def __init__(self, models_dir=MODELS_DIR):
        self.models_dir = models_dir
        self._models: Dict[str, SOHModel] = {}
        self._detectors: Dict[str, AnomalyDetector] = {}

    def _model(self, tier_key: str) -> SOHModel:
        if tier_key not in self._models:
            self._models[tier_key] = SOHModel.load(
                self.models_dir, variant=f"tier_{tier_key}"
            )
        return self._models[tier_key]

    def _detector(self, feature_set: str) -> AnomalyDetector:
        if feature_set not in self._detectors:
            self._detectors[feature_set] = AnomalyDetector.load(
                self.models_dir, feature_set=feature_set
            )
        return self._detectors[feature_set]

    # -----------------------------------------------------------------------
    def assess(
        self,
        row: pd.DataFrame,
        tier: InputTier,
        assumptions: Optional[List[str]] = None,
        measured_capacity_ah: Optional[float] = None,
    ) -> Dict:
        """Full assessment of a single unseen battery."""
        assumptions = list(assumptions or [])
        record = row.iloc[0]
        format_key = str(record["format_key"])
        fmt = get_format(format_key)
        battery_id = str(record.get("battery_id") or "USER-BATTERY")

        transfer = chemistry_transfer_note(format_key)
        model = self._model(tier.key)
        validation = model.metadata.get("validation", {})

        # -- SOH estimate ----------------------------------------------------
        prediction = model.predict_full(row)[0]

        # Increases uncertainty when the battery chemistry differs from the training data.
        # This is added on top of the normal model uncertainty.
        factor = transfer["interval_factor"]
        lower = prediction.soh - factor * \
            (prediction.soh - prediction.soh_lower)
        upper = prediction.soh + factor * \
            (prediction.soh_upper - prediction.soh)
        lower = float(np.clip(lower, 0.0, 1.05))
        upper = float(np.clip(upper, 0.0, 1.05))
        interval_width = upper - lower

        # -- anomalies -------------------------------------------------------
        detector_set = "charge_only" if tier.rank <= 2 else "charge_only"
        anomaly = self._detector(detector_set).detect_single(record, fmt)

        # -- safety ----------------------------------------------------------
        peak_temp = record.get("ch_temp_max_c", np.nan)
        safety = assess_safety(
            soh=prediction.soh,
            fmt=fmt,
            anomaly=anomaly,
            rct_growth=None,           # needs an as-new baseline for this unit
            peak_temp_c=float(peak_temp) if np.isfinite(peak_temp) else None,
            fade_slope_per_cycle=None,  # needs history
            soh_uncertainty=interval_width,
        )

        # -- explanation -----------------------------------------------------
        feature_values = {
            name: (float(record[name])
                   if name in record and np.isfinite(record[name]) else None)
            for name in model.features
        }
        factors = explain_prediction(prediction.contributions, feature_values)

        # -- second life -----------------------------------------------------
        if tier.reliable:
            second_life = grade_second_life(
                prediction.soh, fmt, safety, soh_lower=lower, soh_upper=upper
            )
        else:
           # Tier 4 has low accuracy, so it is not reliable enough for making reuse
           # decisions. It only provides an indicative estimate.
            second_life = {
                "grade": "NOT_GRADED",
                "recommendation": (
                    "Insufficient information to assign a reuse grade."
                ),
                "rationale": (
                    f"Input reached only tier {tier.rank} "
                    f"({tier.display_name}), which measures "
                    f"{validation.get('mae_soh_percentage_points', 'n/a')} SOH "
                    f"points mean error and R2 "
                    f"{validation.get('r2', 'n/a')} in cross-validation. That is "
                    "too imprecise to separate reuse grades."
                ),
                "grading_basis": "not graded",
                "grade_confidence": "INSUFFICIENT",
                "grade_is_ambiguous": True,
                "worst_case_grade": None,
                "best_case_grade": None,
                "confidence_interval_width_soh_points": round(100 * interval_width, 1),
                "next_step": (
                    "Supply the charging figures requested at tier 3 -- charging "
                    "current, steady-phase duration, taper duration and total "
                    "charge delivered -- to obtain a grade."
                ),
                "safety_override_applied": False,
                "estimated_remaining_energy_wh": round(
                    prediction.soh * fmt.rated_energy_wh, 1
                ),
            }

        # -- optional direct measurement -------------------------------------
        measurement = None
        if measured_capacity_ah is not None and np.isfinite(measured_capacity_ah):
            measurement = direct_measurement(measured_capacity_ah, format_key)
            measurement["estimation_error_percentage_points"] = round(
                100 * (prediction.soh - measurement["soh"]), 2
            )
            measurement["within_confidence_interval"] = bool(
                lower <= measurement["soh"] <= upper
            )

        return {
            "battery_id": battery_id,
            "format": fmt.as_dict(),
            "is_unseen_battery": True,
            "cycle_index": (int(record["cycle_index"])
                            if np.isfinite(record.get("cycle_index", np.nan)) else None),
            "total_cycles_observed": 1,
            "timestamp": str(record.get("timestamp", "")),

            "input_tier": {
                **tier.as_dict(),
                "measured_accuracy": validation,
                "interval_calibration_factor": round(model.calibration_factor, 3),
            },
            "assumptions": assumptions,
            "chemistry_transfer": transfer,

            "health": {
                "soh": round(prediction.soh, 4),
                "soh_percent": round(100 * prediction.soh, 2),
                "confidence_interval_90": [round(lower, 4), round(upper, 4)],
                "interval_width": round(interval_width, 4),
                "state_of_health_label": self._label(prediction.soh, fmt),
                "remaining_capacity_ah": round(
                    prediction.soh * fmt.rated_capacity_ah, 3
                ),
                "eol_threshold": fmt.eol_soh,
                "past_first_life_eol": bool(prediction.soh < fmt.eol_soh),
                # Explicitly null rather than 0: these need history that does not
                # exist, and a zero here would read as "no fade acceleration".
                "fade_rate_soh_points_per_100_cycles": None,
            },

            "unavailable_analyses": [
                {
                    "analysis": "Fade-rate / ageing-knee detection",
                    "reason": "Requires several cycles of history for this unit.",
                    "how_to_enable": "Upload two or more charge cycles recorded "
                                     "weeks apart.",
                },
                {
                    "analysis": "Resistance growth versus as-new",
                    "reason": "Requires a commissioning baseline for this unit.",
                    "how_to_enable": "Supply impedance values recorded when the "
                                     "battery was new, if they exist.",
                },
                {
                    "analysis": "Trajectory anomaly detection",
                    "reason": "Compares a cycle against the same cell's recent "
                              "past, which is unavailable for a single cycle.",
                    "how_to_enable": "Upload a sequence of consecutive cycles.",
                },
            ],

            "degradation_factors": [f.as_dict() for f in factors],
            "degradation_summary": summarise_factors(factors),
            "explanation_caveat": EXPLANATION_CAVEAT,

            "anomaly": anomaly.as_dict(),
            "safety": safety.as_dict(),
            "second_life": second_life,
            "reference_measurement": measurement,

            "model_provenance": {
                "soh_model_variant": f"tier_{tier.key}",
                "input_tier": tier.key,
                "soh_features_used": len(model.features),
                "training_batteries": model.metadata.get("training_batteries"),
                "training_cycles": model.metadata.get("n_training_cycles"),
                "training_data_sha256": model.metadata.get("training_data_sha256"),
                "training_chemistries": sorted(TRAINED_CHEMISTRIES),
                "interval_calibration_factor": round(model.calibration_factor, 3),
                "cross_chemistry_interval_factor": factor,
                "validation_method": "leave-one-battery-out cross-validation",
                "validation_mae_soh_points":
                    validation.get("mae_soh_percentage_points"),
                "validation_r2": validation.get("r2"),
                "validation_worst_battery_mae_soh_points":
                    validation.get("worst_battery_mae_soh_points"),
            },

            "trajectory": None,
        }

    @staticmethod
    def _label(soh: float, fmt) -> str:
        if soh >= 0.95:
            return "As-new"
        if soh >= fmt.eol_soh:
            return "Healthy"
        if soh >= 0.70:
            return "Degraded (second-life candidate)"
        if soh >= fmt.second_life_floor_soh:
            return "Heavily degraded"
        return "End of usable life"

    # -----------------------------------------------------------------------
    def issue_passport(self, assessment: Dict, private_key) -> Dict:
        """Creates a signed passport for a battery without previous history.

        The passport includes the input tier and model accuracy so users can understand
        both the estimated result and the reliability of that estimate.
        """
        from .passport import build_passport, sign_passport

        notes = [assessment["degradation_summary"]]
        if assessment["assumptions"]:
            notes.append("Assumptions made during onboarding: "
                         + " ".join(assessment["assumptions"]))
        if not assessment["chemistry_transfer"]["in_distribution"]:
            notes.append(assessment["chemistry_transfer"]["note"])

        payload = build_passport(
            battery_id=assessment["battery_id"],
            format_spec={
                "format_key": assessment["format"]["key"],
                "display_name": assessment["format"]["display_name"],
                "chemistry": assessment["format"]["chemistry"],
                "form_factor": assessment["format"]["form_factor"],
                "rated_capacity_ah": assessment["format"]["rated_capacity_ah"],
                "nominal_voltage_v": assessment["format"]["nominal_voltage_v"],
            },
            health={
                **assessment["health"],
                "input_tier": assessment["input_tier"]["key"],
                "input_tier_name": assessment["input_tier"]["display_name"],
                "input_tier_measured_accuracy":
                    assessment["input_tier"]["measured_accuracy"],
                "onboarding_assumptions": assessment["assumptions"],
                "unavailable_analyses": [
                    a["analysis"] for a in assessment["unavailable_analyses"]
                ],
            },
            degradation_factors=assessment["degradation_factors"],
            safety=assessment["safety"],
            second_life=assessment["second_life"],
            anomaly_summary=assessment["anomaly"],
            model_provenance=assessment["model_provenance"],
            certified_test=None,
            notes=" ".join(notes),
        )
        payload["chemistry_transfer"] = assessment["chemistry_transfer"]
        return sign_passport(payload, private_key)
