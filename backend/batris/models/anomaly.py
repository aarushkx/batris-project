"""
Battery anomaly detection.

This file detects unusual battery behaviour.

An anomaly does not mean normal ageing.

A battery losing capacity over time is expected.

An anomaly means the battery behaves differently
from what is normally expected.

Examples:
- Temperature suddenly increases
- Resistance rises quickly
- Charging stops early
- Voltage goes below safe limits


Three detection methods are combined:

1. Physical rules:
   Checks battery limits from the format specification.

2. Isolation Forest:
   Finds unusual combinations of measurements.

3. Trajectory check:
   Finds sudden changes compared to the battery's own history.


Using multiple methods makes detection more reliable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ..formats import BatteryFormat, get_format

logger = logging.getLogger(__name__)

# Features used to detect unusual battery behaviour.
# Includes charge, temperature, resistance and discharge data.
# SOH and capacity test values are excluded because they are used for ageing
# estimation, not anomaly detection.
ANOMALY_FEATURES: List[str] = [
    # charge behaviour
    "cc_capacity_frac", "cv_capacity_frac", "cc_cv_ah_ratio", "cc_time_fraction",
    "total_charge_frac", "mean_charge_c_rate", "dvdt_cc_per_frac", "v_norm_at_cc_end",
    # thermal behaviour
    "ch_temp_max_c", "ch_temp_rise_c", "ch_thermal_dose_c_h",
    # resistance
    "ohmic_r_norm", "re_norm", "rct_norm",
    # discharge behaviour
    "audit_dis_temp_max_c", "audit_dis_temp_rise_c", "audit_min_v_norm",
    "audit_mean_dis_c_rate", "audit_dis_thermal_dose_c_h",
]

# Charge-only features used when only a charge cycle is available.
# A separate model is trained because missing discharge data should not be filled
# with average values, as it can hide real anomalies.
CHARGE_ANOMALY_FEATURES: List[str] = [
    "cc_capacity_frac", "cv_capacity_frac", "cc_cv_ah_ratio", "cc_time_fraction",
    "total_charge_frac", "mean_charge_c_rate", "dvdt_cc_per_frac", "v_norm_at_cc_end",
    "ch_temp_max_c", "ch_temp_rise_c", "ch_thermal_dose_c_h", "ohmic_r_norm",
]

FEATURE_SETS: Dict[str, List[str]] = {
    "full": ANOMALY_FEATURES,
    "charge_only": CHARGE_ANOMALY_FEATURES,
}

SEVERITY_ORDER = {"none": 0, "info": 1, "warning": 2, "critical": 3}


@dataclass
class Anomaly:
    """One detected abnormality."""

    code: str
    severity: str          # info | warning | critical
    detail: str            # human-readable, with the measured value
    evidence: Dict[str, float] = field(default_factory=dict)
    source: str = "rule"   # rule | statistical | trajectory

    def as_dict(self) -> Dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "detail": self.detail,
            "source": self.source,
            "evidence": {k: round(float(v), 4) for k, v in self.evidence.items()},
        }


@dataclass
class AnomalyResult:
    """All anomalies found for a single cycle, plus a combined score."""

    anomalies: List[Anomaly] = field(default_factory=list)
    isolation_score: float = 0.0     # raw IsolationForest decision function
    trajectory_residual: float = 0.0
    score: float = 0.0               # 0-100, higher = more abnormal
    # Which detectors actually ran. Populated by detect_single(), where some are
    # unavailable; a caller must be able to tell "nothing found" from
    # "nothing looked".
    detectors_run: Dict[str, bool] = field(
        default_factory=lambda: {"physical_rules": True,
                                 "statistical_outlier": True,
                                 "trajectory_deviation": True}
    )
    coverage_note: str = "All three detectors ran."

    @property
    def max_severity(self) -> str:
        if not self.anomalies:
            return "none"
        return max((a.severity for a in self.anomalies), key=lambda s: SEVERITY_ORDER[s])

    @property
    def is_anomalous(self) -> bool:
        return SEVERITY_ORDER[self.max_severity] >= SEVERITY_ORDER["warning"]

    def as_dict(self) -> Dict:
        return {
            "anomaly_score": round(self.score, 1),
            "max_severity": self.max_severity,
            "is_anomalous": self.is_anomalous,
            "n_anomalies": len(self.anomalies),
            "anomalies": [a.as_dict() for a in self.anomalies],
            "isolation_score": round(self.isolation_score, 4),
            "trajectory_residual": round(self.trajectory_residual, 4),
            "detectors_run": self.detectors_run,
            "coverage_note": self.coverage_note,
        }


# ===========================================================================
# Deterministic physical rules
# ===========================================================================

class RuleEngine:
    """Physical limit checks, evaluated against the battery's format spec.

    Every threshold comes from ``built-in battery format registry``, so the same rules apply
    correctly to an LCO 18650 (critical at 50 C) and an LFP prismatic cell
    (critical at 60 C) without any code change.
    """

    # Checks if resistance growth is abnormal compared to the battery's normal ageing.
    # Large sudden increases usually indicate a fault instead of regular degradation.
    RESISTANCE_FAULT_RATIO = 2.0
    RESISTANCE_WARN_RATIO = 1.6

    # Checks if the charge was stopped early or did not complete normally.
    CHARGE_SHORTFALL_FRACTION = 0.70

    def evaluate(self, row: pd.Series, fmt: BatteryFormat,
                 context: Optional[Dict[str, float]] = None) -> List[Anomaly]:
        context = context or {}
        found: List[Anomaly] = []

        found += self._thermal(row, fmt)
        found += self._resistance(row)
        found += self._voltage(row, fmt)
        found += self._charge_completion(row, context)
        found += self._c_rate(row, fmt)
        found += self._low_temp_charging(row, fmt)
        return found

    # -- individual checks ---------------------------------------------------
    def _thermal(self, row, fmt) -> List[Anomaly]:
        """Checks battery temperature limits during charging and discharging.
        Charging has stricter temperature limits, so both conditions are checked
        separately to avoid missing problems or creating false alerts.
        """
        found: List[Anomaly] = []

        charge_peak = row.get("ch_temp_max_c", np.nan)
        if np.isfinite(charge_peak) and charge_peak > fmt.temp_max_charge_c:
            found.append(Anomaly(
                "CHARGE_OVERTEMPERATURE", "critical",
                f"Cell reached {charge_peak:.1f} C while charging, above the "
                f"{fmt.temp_max_charge_c:.0f} C charge ceiling. Charging a hot cell "
                "drives electrolyte decomposition and gas generation.",
                {"charge_peak_c": charge_peak, "limit_c": fmt.temp_max_charge_c},
            ))

        peak = np.nanmax(
            [charge_peak, row.get("audit_dis_temp_max_c", np.nan)])
        if not np.isfinite(peak):
            return found

        if peak >= fmt.temp_critical_c:
            found.append(Anomaly(
                "THERMAL_EXCURSION_CRITICAL", "critical",
                f"Peak cell temperature {peak:.1f} C reached the critical limit of "
                f"{fmt.temp_critical_c:.0f} C. Separator integrity and thermal "
                "runaway margin are both compromised in this range.",
                {"peak_temp_c": peak, "limit_c": fmt.temp_critical_c},
            ))
        elif peak >= fmt.temp_warn_c:
            found.append(Anomaly(
                "THERMAL_EXCURSION", "warning",
                f"Peak cell temperature {peak:.1f} C exceeded the "
                f"{fmt.temp_warn_c:.0f} C advisory limit, where side-reaction "
                "rates rise steeply.",
                {"peak_temp_c": peak, "limit_c": fmt.temp_warn_c},
            ))
        return found

    def _resistance(self, row) -> List[Anomaly]:
        found = []
        for key, label in (("rct_growth_ratio", "Charge-transfer"),
                           ("re_growth_ratio", "Electrolyte")):
            ratio = row.get(key, np.nan)
            if not np.isfinite(ratio):
                continue
            if ratio >= self.RESISTANCE_FAULT_RATIO:
                found.append(Anomaly(
                    "RESISTANCE_FAULT", "critical",
                    f"{label} resistance is {ratio:.2f}x its as-new baseline. "
                    "Growth this large points to electrode or interconnect "
                    "degradation rather than normal ageing.",
                    {key: ratio, "threshold": self.RESISTANCE_FAULT_RATIO},
                ))
            elif ratio >= self.RESISTANCE_WARN_RATIO:
                found.append(Anomaly(
                    "RESISTANCE_ELEVATED", "warning",
                    f"{label} resistance has risen to {ratio:.2f}x baseline, "
                    "reducing power capability and increasing self-heating.",
                    {key: ratio, "threshold": self.RESISTANCE_WARN_RATIO},
                ))
        return found

    def _voltage(self, row, fmt) -> List[Anomaly]:
        """Checks for undervoltage conditions.
        Separates normal deep discharge warnings from voltage levels that can damage
        the battery and cause safety issues.
        """
        min_v = row.get("audit_min_voltage_v", np.nan)
        if not np.isfinite(min_v):
            return []

        if min_v < fmt.v_min_absolute:
            return [Anomaly(
                "UNDERVOLTAGE", "critical",
                f"Cell was discharged to {min_v:.2f} V, below the "
                f"{fmt.v_min_absolute:.2f} V damage floor. Copper dissolution at "
                "this depth can seed internal short paths.",
                {"min_voltage_v": min_v, "limit_v": fmt.v_min_absolute},
            )]
        if min_v < fmt.v_min:
            return [Anomaly(
                "DEEP_DISCHARGE_ADVISORY", "info",
                f"Cell reached {min_v:.2f} V, below the {fmt.v_min:.2f} V "
                "recommended cutoff. Not damaging in itself, but habitual deep "
                "discharge shortens service life.",
                {"min_voltage_v": min_v, "limit_v": fmt.v_min},
            )]
        return []

    def _charge_completion(self, row, context) -> List[Anomaly]:
        actual = row.get("total_charge_frac", np.nan)
        expected = context.get("expected_charge_frac", np.nan)
        if not (np.isfinite(actual) and np.isfinite(expected)) or expected <= 0:
            return []
        if actual < self.CHARGE_SHORTFALL_FRACTION * expected:
            return [Anomaly(
                "INCOMPLETE_CHARGE", "warning",
                f"This charge delivered {actual:.2f} of rated capacity against a "
                f"recent norm of {expected:.2f}, suggesting the session was "
                "interrupted or the charger faulted.",
                {"charge_frac": actual, "expected": expected},
            )]
        return []

    def _c_rate(self, row, fmt) -> List[Anomaly]:
        found = []
        charge_c = row.get("mean_charge_c_rate", np.nan)
        if np.isfinite(charge_c) and charge_c > fmt.max_charge_c_rate * 1.05:
            found.append(Anomaly(
                "OVER_C_RATE_CHARGE", "warning",
                f"Average charge rate {charge_c:.2f}C exceeded the "
                f"{fmt.max_charge_c_rate:.2f}C rating, promoting lithium plating.",
                {"c_rate": charge_c, "limit": fmt.max_charge_c_rate},
            ))
        dis_c = row.get("audit_mean_dis_c_rate", np.nan)
        if np.isfinite(dis_c) and dis_c > fmt.max_discharge_c_rate * 1.05:
            found.append(Anomaly(
                "OVER_C_RATE_DISCHARGE", "warning",
                f"Average discharge rate {dis_c:.2f}C exceeded the "
                f"{fmt.max_discharge_c_rate:.2f}C rating, raising heat generation.",
                {"c_rate": dis_c, "limit": fmt.max_discharge_c_rate},
            ))
        return found

    def _low_temp_charging(self, row, fmt) -> List[Anomaly]:
        """Checks for charging at low temperature.
        Cold charging can cause lithium plating, which may damage the battery and
        create safety risks.
        """
        start_temp = row.get("ch_temp_mean_c", np.nan)
        if np.isfinite(start_temp) and start_temp < fmt.temp_min_charge_c:
            return [Anomaly(
                "LOW_TEMPERATURE_CHARGING", "critical",
                f"Charging proceeded at {start_temp:.1f} C, below the "
                f"{fmt.temp_min_charge_c:.0f} C minimum. Lithium plating at low "
                "temperature is irreversible and creates internal short risk.",
                {"temp_c": start_temp, "limit_c": fmt.temp_min_charge_c},
            )]
        return []


# ===========================================================================
# Combined detector
# ===========================================================================

class AnomalyDetector:
    """Rules + IsolationForest + trajectory residual."""

    def __init__(self, contamination: float = 0.02, random_state: int = 42,
                 feature_set: str = "full"):
        self.contamination = contamination
        self.random_state = random_state
        self.feature_set = feature_set
        self.features = list(FEATURE_SETS[feature_set])
        self.forest: Optional[IsolationForest] = None
        self.medians: Optional[pd.Series] = None   # for NaN imputation
        self.score_threshold: float = 0.0
        self.metadata: Dict = {}
        self.rules = RuleEngine()

    # -- training ------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "AnomalyDetector":
        """Trains the model to learn normal battery behaviour.
        The training data should mostly contain normal cycles so the model can identify
        cycles that behave differently from normal ageing.
        """
        X = df[self.features].copy()
        # IsolationForest cannot handle missing values, so missing data is filled with
        # median values before training.
        self.medians = X.median(numeric_only=True)
        X = X.fillna(self.medians)

        self.forest = IsolationForest(
            n_estimators=300,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        ).fit(X)

        scores = self.forest.decision_function(X)
        # Anything below this is in the tail of the training distribution.
        self.score_threshold = float(np.quantile(scores, self.contamination))

        self.metadata = {
            "feature_set": self.feature_set,
            "features": self.features,
            "n_training_cycles": int(len(X)),
            "contamination": self.contamination,
            "score_threshold": self.score_threshold,
            "training_batteries": sorted(df["battery_id"].unique().tolist()),
        }
        logger.info("Fitted anomaly detector on %d cycles (threshold %.4f)",
                    len(X), self.score_threshold)
        return self

    # -- inference -----------------------------------------------------------
    def _isolation_scores(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.features].fillna(self.medians)
        return self.forest.decision_function(X)

    def detect(
        self,
        df: pd.DataFrame,
        context_window: int = 10,
    ) -> List[AnomalyResult]:
        """Evaluate every row. ``df`` must be sorted by battery and cycle."""
        if self.forest is None:
            raise RuntimeError("Detector not fitted. Call fit() or load().")

        iso_scores = self._isolation_scores(df)

        # Stores the battery's recent behaviour history.
        # Used to detect sudden changes in charging or resistance values.
        grouped = df.groupby("battery_id", sort=False)
        expected_charge = grouped["total_charge_frac"].transform(
            lambda s: s.shift(1).rolling(
                context_window, min_periods=3).median()
        )
        rct_recent = grouped["rct_norm"].transform(
            lambda s: s.shift(1).rolling(
                context_window, min_periods=3).median()
        )

        results: List[AnomalyResult] = []
        for position, (_, row) in enumerate(df.iterrows()):
            fmt = get_format(row["format_key"])
            context = {"expected_charge_frac": expected_charge.iloc[position]}

            anomalies = self.rules.evaluate(row, fmt, context)

            # -- statistical -------------------------------------------------
            iso = float(iso_scores[position])
            if iso < self.score_threshold:
                anomalies.append(Anomaly(
                    "STATISTICAL_OUTLIER", "warning",
                    "This cycle's combination of charge, thermal and resistance "
                    "measurements does not match any pattern seen in normal "
                    "operation at any age.",
                    {"isolation_score": iso, "threshold": self.score_threshold},
                    source="statistical",
                ))

            # -- trajectory --------------------------------------------------
            # A sudden resistance step is a fault signature even when the
            # absolute value is still within limits.
            residual = 0.0
            baseline = rct_recent.iloc[position]
            current = row.get("rct_norm", np.nan)
            if np.isfinite(baseline) and np.isfinite(current) and baseline > 0:
                residual = float((current - baseline) / baseline)
                if residual > 0.25:
                    anomalies.append(Anomaly(
                        "RESISTANCE_STEP", "warning",
                        f"Charge-transfer resistance rose {100 * residual:.0f}% "
                        f"above its own {context_window}-cycle norm. Step changes "
                        "indicate a developing fault, not gradual ageing.",
                        {"step_fraction": residual},
                        source="trajectory",
                    ))

            results.append(AnomalyResult(
                anomalies=anomalies,
                isolation_score=iso,
                trajectory_residual=residual,
                score=self._combine(anomalies, iso),
            ))
        return results

    def detect_single(self, row: pd.Series, fmt) -> AnomalyResult:
        """Checks a single battery cycle without previous history.
        Some detectors are skipped because they need past cycle data.
        The isolation model runs only when all required features are available.
        The result also shows which detectors were used.
        """
        anomalies = self.rules.evaluate(row, fmt, context={})

        iso_score = 0.0
        forest_ran = False
        if self.forest is not None:
            values = {f: row.get(f, np.nan) for f in self.features}
            if all(np.isfinite(v) for v in values.values()):
                frame = pd.DataFrame([values])[self.features]
                iso_score = float(self.forest.decision_function(frame)[0])
                forest_ran = True
                if iso_score < self.score_threshold:
                    anomalies.append(Anomaly(
                        "STATISTICAL_OUTLIER", "warning",
                        "This charge does not match any pattern seen in normal "
                        "operation at any age.",
                        {"isolation_score": iso_score,
                         "threshold": self.score_threshold},
                        source="statistical",
                    ))

        result = AnomalyResult(
            anomalies=anomalies,
            isolation_score=iso_score,
            trajectory_residual=0.0,
            score=self._combine(anomalies, iso_score if forest_ran
                                else self.score_threshold + 1.0),
        )
        result.detectors_run = {
            "physical_rules": True,
            "statistical_outlier": forest_ran,
            "trajectory_deviation": False,
        }
        result.coverage_note = (
            "All three detectors ran."
            if forest_ran else
            "Only the physical limit checks ran. The statistical detector needs a "
            "complete charge curve, and the trajectory detector needs cycle "
            "history. A clean result here is therefore weaker evidence than a "
            "clean result on a battery with recorded history."
        )
        return result

    def _combine(self, anomalies: List[Anomaly], iso_score: float) -> float:
        """Combines all detected issues into a single 0-100 anomaly score.
        Critical issues have higher priority, while multiple smaller issues slightly
        increase the overall score.
        """
        if not anomalies:
            base = 0.0
        else:
            weights = {"info": 20.0, "warning": 55.0, "critical": 90.0}
            base = max(weights[a.severity] for a in anomalies)
            # breadth bonus, capped
            base += min(10.0, 3.0 * (len(anomalies) - 1))

        # Continuous nudge from how far outside the normal manifold we are, so
        # near-threshold cycles do not sit at exactly zero.
        if iso_score < self.score_threshold:
            margin = min(1.0, abs(iso_score - self.score_threshold) / 0.15)
            base = max(base, 40.0 + 30.0 * margin)
        return float(np.clip(base, 0.0, 100.0))

    # -- persistence ---------------------------------------------------------
    def save(self, directory: Path | str) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "forest": self.forest,
                "medians": self.medians,
                "score_threshold": self.score_threshold,
                "contamination": self.contamination,
                "feature_set": self.feature_set,
                "features": self.features,
            },
            directory / f"anomaly_detector_{self.feature_set}.joblib",
        )
        with open(directory / f"anomaly_meta_{self.feature_set}.json", "w",
                  encoding="utf-8") as fh:
            json.dump(self.metadata, fh, indent=2)
        logger.info("Saved anomaly detector (%s) to %s",
                    self.feature_set, directory)
        return directory / f"anomaly_detector_{self.feature_set}.joblib"

    @classmethod
    def load(cls, directory: Path | str, feature_set: str = "full") -> "AnomalyDetector":
        directory = Path(directory)
        path = directory / f"anomaly_detector_{feature_set}.joblib"
        if not path.exists():
            raise FileNotFoundError(
                f"No trained detector at {path}. Run:  python -m backend.batris.train_anomaly"
            )
        blob = joblib.load(path)
        detector = cls(contamination=blob["contamination"],
                       feature_set=blob.get("feature_set", feature_set))
        detector.forest = blob["forest"]
        detector.medians = blob["medians"]
        detector.score_threshold = blob["score_threshold"]
        detector.features = blob.get(
            "features", list(FEATURE_SETS[feature_set]))

        meta_path = directory / f"anomaly_meta_{feature_set}.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as fh:
                detector.metadata = json.load(fh)
        return detector
