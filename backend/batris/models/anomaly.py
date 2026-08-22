"""
Battery anomaly detection system.

This file checks whether a battery cycle is behaving differently
from normal battery behaviour.

Important:
Battery ageing itself is not considered an anomaly.

Example:
A battery losing capacity after many cycles is normal.

But these can be anomalies:
- Battery temperature becomes unusually high.
- Internal resistance suddenly increases.
- Charging stops earlier than expected.
- Battery behaviour is different from normal batteries.

The system uses three methods:

1. Rule Engine
   Checks fixed battery safety limits.

2. Isolation Forest
   Uses machine learning to find unusual patterns.

3. Trajectory Detection
   Checks if a battery suddenly changes compared
   to its own previous cycles.

All three results are combined to create one anomaly score.
"""


from __future__ import annotations

import logging

from dataclasses import dataclass, field

from typing import Dict, List


logger = logging.getLogger(__name__)


# Features used to detect unusual battery behaviour.
#
# These describe:
# - Charging behaviour
# - Temperature behaviour
# - Resistance changes
# - Discharging behaviour
#
# These are different from SOH features because anomaly detection
# focuses on finding abnormal events, not predicting battery age.
ANOMALY_FEATURES: List[str] = [

    # Charging related features
    "cc_capacity_frac",
    "cv_capacity_frac",
    "cc_cv_ah_ratio",
    "cc_time_fraction",
    "total_charge_frac",
    "mean_charge_c_rate",
    "dvdt_cc_per_frac",
    "v_norm_at_cc_end",

    # Temperature related features
    "ch_temp_max_c",
    "ch_temp_rise_c",
    "ch_thermal_dose_c_h",

    # Resistance related features
    "ohmic_r_norm",
    "re_norm",
    "rct_norm",

    # Discharge related features
    "audit_dis_temp_max_c",
    "audit_dis_temp_rise_c",
    "audit_min_v_norm",
    "audit_mean_dis_c_rate",
    "audit_dis_thermal_dose_c_h",
]


# Features used when only charging data is available.
#
# Example:
# A user uploads only a charging cycle.
#
# We do not fill missing discharge values with fake values because
# that could hide real problems.
CHARGE_ANOMALY_FEATURES: List[str] = [

    # Charging behaviour
    "cc_capacity_frac",
    "cv_capacity_frac",
    "cc_cv_ah_ratio",
    "cc_time_fraction",
    "total_charge_frac",
    "mean_charge_c_rate",
    "dvdt_cc_per_frac",
    "v_norm_at_cc_end",

    # Temperature behaviour
    "ch_temp_max_c",
    "ch_temp_rise_c",
    "ch_thermal_dose_c_h",

    # Resistance behaviour
    "ohmic_r_norm",
]


# Available feature modes.
#
# full:
#     Uses charging, temperature, resistance and discharge features.
#
# charge_only:
#     Uses only charging information.
FEATURE_SETS: Dict[str, List[str]] = {
    "full": ANOMALY_FEATURES,
    "charge_only": CHARGE_ANOMALY_FEATURES,
}


# Used to compare anomaly severity levels.
SEVERITY_ORDER = {
    "none": 0,
    "info": 1,
    "warning": 2,
    "critical": 3
}


@dataclass
class Anomaly:
    """
    Stores one detected battery problem.

    Example:

    Code:
        HIGH_TEMPERATURE

    Severity:
        warning

    Detail:
        Battery temperature exceeded limit.

    Evidence:
        Actual temperature and allowed temperature.
    """

    code: str

    # Severity can be:
    # info, warning, critical
    severity: str

    # Human-readable explanation.
    detail: str

    # Values that caused this anomaly.
    evidence: Dict[str, float] = field(
        default_factory=dict
    )

    # Which detector found it:
    # rule, statistical, trajectory
    source: str = "rule"

    def as_dict(self) -> Dict:
        """
        Convert anomaly information into dictionary format.
        """

        return {
            "code": self.code,

            "severity": self.severity,

            "detail": self.detail,

            "source": self.source,

            "evidence": {
                key: round(float(value), 4)
                for key, value in self.evidence.items()
            },
        }


@dataclass
class AnomalyResult:
    """
    Stores all anomaly information for one battery cycle.

    It contains:
    - Detected problems
    - Isolation Forest score
    - Sudden change score
    - Final anomaly score
    """

    # List of detected issues.
    anomalies: List[Anomaly] = field(
        default_factory=list
    )

    # Score from Isolation Forest.
    isolation_score: float = 0.0

    # Measures sudden changes compared to previous cycles.
    trajectory_residual: float = 0.0

    # Final anomaly score from 0-100.
    score: float = 0.0

    # Shows which detectors were actually used.
    #
    # Some detectors need history, so they may not always run.
    detectors_run: Dict[str, bool] = field(
        default_factory=lambda: {
            "physical_rules": True,
            "statistical_outlier": True,
            "trajectory_deviation": True
        }
    )

    # Explanation of detector availability.
    coverage_note: str = (
        "All three detectors ran."
    )

    @property
    def max_severity(self) -> str:
        """
        Return the highest severity problem found.
        """

        if not self.anomalies:
            return "none"

        return max(
            (
                a.severity
                for a in self.anomalies
            ),
            key=lambda s: SEVERITY_ORDER[s]
        )

    @property
    def is_anomalous(self) -> bool:
        """
        Return True if the battery has a warning
        or critical issue.
        """

        return (
            SEVERITY_ORDER[self.max_severity]
            >=
            SEVERITY_ORDER["warning"]
        )

    def as_dict(self) -> Dict:
        """
        Convert the complete result into dictionary format.
        """

        return {
            "anomaly_score":
                round(self.score, 1),

            "max_severity":
                self.max_severity,

            "is_anomalous":
                self.is_anomalous,

            "n_anomalies":
                len(self.anomalies),

            "anomalies":
                [
                    a.as_dict()
                    for a in self.anomalies
                ],

            "isolation_score":
                round(self.isolation_score, 4),

            "trajectory_residual":
                round(self.trajectory_residual, 4),

            "detectors_run":
                self.detectors_run,

            "coverage_note":
                self.coverage_note,
        }
