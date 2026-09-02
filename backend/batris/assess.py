"""
Main pipeline that converts battery cycle data into a complete report.

All parts of the system use this function to get battery assessment results.
Keeping everything in one place ensures the API, CLI and frontend show the
same information.
"""

from __future__ import annotations

from .paths import MODELS_DIR

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .explain import EXPLANATION_CAVEAT, explain_prediction, summarise_factors
from .formats import get_format
from .models.anomaly import AnomalyDetector
from .models.soh import DEFAULT_PARAMS, SOHModel
from .features import SOH_FEATURES
from .passport import build_passport, sign_passport
from .safety import assess_safety, grade_second_life

logger = logging.getLogger(__name__)


def build_lobo_trajectory_cache(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Precompute the exact LOBO XGBoost predictions used by evaluate.py.

    This intentionally mirrors evaluate.lobo_predictions: one XGBoost model is
    fit for each held-out battery using the other batteries as training data.
    """
    import xgboost as xgb

    required = {"battery_id", "soh", *SOH_FEATURES}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Cannot build LOBO cache; missing columns: {missing}")

    features = list(SOH_FEATURES)
    cache: Dict[str, np.ndarray] = {}

    for held_out in sorted(df["battery_id"].unique()):
        train = df[df["battery_id"] != held_out]
        test = df[df["battery_id"] == held_out].sort_values("cycle_index")

        model = xgb.XGBRegressor(
            objective="reg:squarederror",
            **DEFAULT_PARAMS,
        )
        model.fit(train[features], train["soh"])
        cache[str(held_out)] = model.predict(test[features])

    return cache


class BatteryAssessor:
    """Loads the trained models once and applies them to battery histories."""

    def __init__(self, models_dir: Path | str = MODELS_DIR,
                 variant: str = "full",
                 lobo_trajectories: Optional[Dict[str, np.ndarray]] = None):
        self.models_dir = Path(models_dir)
        self.variant = variant
        self.lobo_trajectories = lobo_trajectories or {}
        self.soh_model = SOHModel.load(self.models_dir, variant=variant)
        self.anomaly_detector = AnomalyDetector.load(self.models_dir)
        logger.info("Loaded models (SOH variant=%s) from %s",
                    variant, models_dir)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _fade_slope(soh_series: np.ndarray, window: int = 30) -> Optional[float]:
        """Calculates the recent SOH loss rate per cycle.

        Uses recent cycles instead of the full battery history because current ageing
        behaviour is more important than the average lifetime degradation rate.
        """
        series = np.asarray(soh_series, dtype=float)
        series = series[np.isfinite(series)]
        if len(series) < 5:
            return None
        recent = series[-window:]
        x = np.arange(len(recent), dtype=float)
        slope, _ = np.polyfit(x, recent, 1)
        return float(slope)

    # -- core ----------------------------------------------------------------
    def assess(
        self,
        history: pd.DataFrame,
        cycle_index: Optional[int] = None,
        include_trajectory: bool = True,
    ) -> Dict:
        """Assesses one battery using its cycle history.

        The latest cycle is evaluated by default, while the complete history is used
        to calculate trends, detect anomalies and understand battery behaviour.
        """
        if history.empty:
            raise ValueError("Empty history supplied")

        history = history.sort_values("cycle_index").reset_index(drop=True)
        battery_id = str(history["battery_id"].iloc[0])
        fmt = get_format(str(history["format_key"].iloc[0]))

        if cycle_index is None:
            position = len(history) - 1
        else:
            matches = history.index[history["cycle_index"] == cycle_index]
            if len(matches) == 0:
                raise ValueError(
                    f"Cycle {cycle_index} not found for {battery_id}. "
                    f"Available range: {history['cycle_index'].min()}-"
                    f"{history['cycle_index'].max()}"
                )
            position = int(matches[0])

        target = history.iloc[[position]]
        row = history.iloc[position]

        # -- SOH estimate ----------------------------------------------------
        prediction = self.soh_model.predict_full(target)[0]

        # -- trajectory of estimates ----------------------------------------
        # The dashboard trajectory is intentionally OUT-OF-SAMPLE for the
        # benchmark dataset: for a selected battery, its battery is held out
        # while XGBoost is trained on the other batteries. This is the same
        # protocol used by evaluate.py, so the trajectory is a genuine
        # generalization result rather than an in-sample fit.
        lobo_series = self.lobo_trajectories.get(battery_id)
        if self.variant == "full" and lobo_series is not None:
            estimated_series = np.asarray(lobo_series, dtype=float)
            trajectory_method = "LOBO XGBoost (battery held out)"
            trajectory_description = (
                f"{battery_id} was excluded from training; XGBoost was trained "
                "on the other batteries and then used to predict this battery."
            )
        else:
            estimated_series = self.soh_model.predict(history)
            trajectory_method = "Full XGBoost (known history)"
            trajectory_description = (
                "Trajectory from the full trained model; this is not an out-of-sample "
                "generalization curve."
            )
        fade_slope = self._fade_slope(estimated_series[: position + 1])

        # -- anomalies -------------------------------------------------------
        anomaly_results = self.anomaly_detector.detect(history)
        anomaly = anomaly_results[position]

        recent_window = anomaly_results[max(0, position - 19): position + 1]
        anomaly_summary = {
            **anomaly.as_dict(),
            "recent_window_cycles": len(recent_window),
            "recent_anomalous_cycles": sum(r.is_anomalous for r in recent_window),
            "recent_critical_cycles": sum(
                r.max_severity == "critical" for r in recent_window
            ),
        }

        # -- safety ----------------------------------------------------------
        peak_temp = float(np.nanmax([
            row.get("ch_temp_max_c", np.nan),
            row.get("audit_dis_temp_max_c", np.nan),
        ]))
        rct_growth = row.get("rct_growth_ratio", np.nan)

        safety = assess_safety(
            soh=prediction.soh,
            fmt=fmt,
            anomaly=anomaly,
            rct_growth=float(rct_growth) if np.isfinite(rct_growth) else None,
            peak_temp_c=peak_temp if np.isfinite(peak_temp) else None,
            fade_slope_per_cycle=fade_slope,
            soh_uncertainty=prediction.interval_width,
        )

        # -- explanation -----------------------------------------------------
        feature_values = {
            name: float(row[name]) if name in row and np.isfinite(
                row[name]) else None
            for name in self.soh_model.features
        }
        factors = explain_prediction(prediction.contributions, feature_values)

        # -- second life -----------------------------------------------------
        second_life = grade_second_life(
            prediction.soh, fmt, safety,
            soh_lower=prediction.soh_lower, soh_upper=prediction.soh_upper,
        )

        # -- reference measurement, when one exists --------------------------
        # The dataset contains actual discharge capacity values, so the demo can compare
        # predictions with real values. In real deployment, this data is usually not
        # available.
        measured = row.get("audit_capacity_ah", np.nan)
        reference: Optional[Dict] = None
        if np.isfinite(measured):
            true_soh = float(measured / fmt.rated_capacity_ah)
            reference = {
                "method": "REFERENCE_MEASUREMENT",
                "method_description": (
                    "Capacity from a full controlled discharge recorded in the "
                    "source dataset. Present here because this is a benchmark "
                    "dataset; a fielded battery would not have this value."
                ),
                "measured_capacity_ah": round(float(measured), 4),
                "measured_soh": round(true_soh, 4),
                "estimation_error_percentage_points": round(
                    100 * (prediction.soh - true_soh), 2
                ),
                "within_confidence_interval": bool(
                    prediction.soh_lower <= true_soh <= prediction.soh_upper
                ),
            }

        validation = (self.soh_model.metadata.get("validation") or {})

        return {
            "battery_id": battery_id,
            "format": fmt.as_dict(),
            "cycle_index": int(row["cycle_index"]),
            "total_cycles_observed": int(len(history)),
            "timestamp": str(row["timestamp"]),

            "health": {
                **prediction.as_dict(),
                "state_of_health_label": self._health_label(prediction.soh, fmt),
                "remaining_capacity_ah": round(
                    prediction.soh * fmt.rated_capacity_ah, 3
                ),
                "eol_threshold": fmt.eol_soh,
                "past_first_life_eol": bool(prediction.soh < fmt.eol_soh),
                "fade_rate_soh_points_per_100_cycles": (
                    round(-100 * 100 * fade_slope,
                          2) if fade_slope is not None else None
                ),
            },

            "degradation_factors": [f.as_dict() for f in factors],
            "degradation_summary": summarise_factors(factors),
            "explanation_caveat": EXPLANATION_CAVEAT,

            "anomaly": anomaly_summary,
            "safety": safety.as_dict(),
            "second_life": second_life,
            "reference_measurement": reference,

            "model_provenance": {
                "soh_model_variant": self.variant,
                "soh_features_used": len(self.soh_model.features),
                "training_batteries": self.soh_model.metadata.get("training_batteries"),
                "training_cycles": self.soh_model.metadata.get("n_training_cycles"),
                "training_data_sha256": self.soh_model.metadata.get("training_data_sha256"),
                "interval_calibration_factor": round(
                    self.soh_model.calibration_factor, 3
                ),
                "validation_method": "leave-one-battery-out cross-validation",
                "validation_mae_soh_points": validation.get("mae_soh_percentage_points"),
                "anomaly_detector_threshold": round(
                    self.anomaly_detector.score_threshold, 5
                ),
            },

            "trajectory": self._trajectory(
                history, estimated_series, anomaly_results,
                method=trajectory_method,
                description=trajectory_description,
            ) if include_trajectory else None,
        }

    @staticmethod
    def _health_label(soh: float, fmt) -> str:
        if soh >= 0.95:
            return "As-new"
        if soh >= fmt.eol_soh:
            return "Healthy"
        if soh >= 0.70:
            return "Degraded (second-life candidate)"
        if soh >= fmt.second_life_floor_soh:
            return "Heavily degraded"
        return "End of usable life"

    @staticmethod
    def _trajectory(
        history: pd.DataFrame,
        estimated: np.ndarray,
        anomaly_results: List,
        method: str = "Full XGBoost (known history)",
        description: str = "",
    ) -> Dict:
        """Series for the dashboard chart."""
        measured = history["audit_capacity_ah"] / history["rated_capacity_ah"]
        # Per-cycle timestamps are what let the health timeline place an event
        # on a date rather than only on a cycle number.
        if "timestamp" in history.columns:
            stamps = [
                None if pd.isna(value) else str(pd.Timestamp(value).isoformat())
                for value in history["timestamp"]
            ]
        else:
            stamps = [None] * len(history)

        return {
            "method": method,
            "description": description,
            "timestamp": stamps,
            "cycle_index": history["cycle_index"].astype(int).tolist(),
            "estimated_soh": [round(float(v), 4) for v in estimated],
            "measured_soh": [
                None if not np.isfinite(v) else round(float(v), 4) for v in measured
            ],
            "anomaly_score": [round(r.score, 1) for r in anomaly_results],
            "anomalous_cycles": [
                int(history["cycle_index"].iloc[i])
                for i, r in enumerate(anomaly_results) if r.is_anomalous
            ],
            # Peak of the charge and discharge maxima, matching what
            # assess_safety() is given for the assessed cycle, so the timeline
            # cannot report a lower peak than the safety module reasoned about.
            "peak_temp_c": [
                None if not np.isfinite(v) else round(float(v), 1)
                for v in np.fmax(
                    history.get(
                        "ch_temp_max_c", pd.Series(np.nan, index=history.index)
                    ).to_numpy(dtype=float),
                    history.get(
                        "audit_dis_temp_max_c", pd.Series(np.nan, index=history.index)
                    ).to_numpy(dtype=float),
                )
            ],
        }

    # -- passport ------------------------------------------------------------
    def issue_passport(
        self,
        history: pd.DataFrame,
        private_key,
        cycle_index: Optional[int] = None,
        include_certified_test: bool = False,
    ) -> Dict:
        """Creates a battery passport from the assessment results.

        Certified test data is optional because normal dataset measurements are not
        official certified tests. This keeps the difference between estimated values
        and verified results clear.
        """
        assessment = self.assess(history, cycle_index=cycle_index,
                                 include_trajectory=False)

        certified = None
        if include_certified_test and assessment.get("reference_measurement"):
            reference = assessment["reference_measurement"]
            certified = {
                "method": "REFERENCE_MEASUREMENT_NOT_ACCREDITED",
                "method_description": (
                    "Capacity from a controlled discharge in the source research "
                    "dataset. Recorded for comparison. This is NOT an accredited "
                    "certification and must not be presented as one."
                ),
                "measured_capacity_ah": reference["measured_capacity_ah"],
                "measured_soh": reference["measured_soh"],
                "source": "NASA Ames Prognostics Data Repository",
            }

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
                "assessed_at_cycle": assessment["cycle_index"],
                "cycles_observed": assessment["total_cycles_observed"],
            },
            degradation_factors=assessment["degradation_factors"],
            safety=assessment["safety"],
            second_life=assessment["second_life"],
            anomaly_summary=assessment["anomaly"],
            model_provenance=assessment["model_provenance"],
            certified_test=certified,
            notes=assessment["degradation_summary"],
        )
        return sign_passport(payload, private_key)
