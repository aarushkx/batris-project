"""
Stage 3: Train and validate the battery anomaly detector.

This file trains the anomaly detection model and checks if it can
find abnormal battery behaviour.

The NASA dataset mostly contains normal battery ageing data and
does not contain labelled faults.

To test the detector, we create artificial faults from normal
battery cycles and check if the model can detect them.

The validation checks:

- Recall: How many faults were detected.
- False alarm rate: How many normal cycles were wrongly flagged.

The artificial faults represent common battery problems:

- Overheating
- Resistance increase
- Charging interruption
- Deep discharge
- Over-rate charging
"""

from __future__ import annotations

from .paths import CYCLES_PATH, MODELS_DIR, REPORTS_DIR

import argparse
import json
import logging
import sys

from pathlib import Path
from typing import Callable, Dict

import numpy as np
import pandas as pd

from .models.anomaly import (
    FEATURE_SETS,
    AnomalyDetector
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("train_anomaly")


# ============================================================
# Synthetic fault generation
# ============================================================
#
# These functions create fake battery faults.
#
# A normal battery cycle is modified to look like
# a real failure case.
#
# These are only used for testing the detector.


def inject_thermal_runaway_precursor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create an overheating problem.

    Represents:
    - Cooling failure
    - Early internal short circuit
    """

    out = df.copy()

    out["ch_temp_max_c"] += 22.0
    out["ch_temp_mean_c"] += 15.0
    out["ch_temp_rise_c"] += 18.0
    out["ch_thermal_dose_c_h"] *= 4.0

    out["audit_dis_temp_max_c"] += 22.0
    out["audit_dis_temp_rise_c"] += 16.0
    out["audit_dis_thermal_dose_c_h"] *= 4.0

    return out


def inject_resistance_fault(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a resistance increase problem.

    Represents:
    - Connector corrosion
    - Electrode damage
    """

    out = df.copy()

    out["rct_norm"] *= 2.2
    out["re_norm"] *= 1.9

    out["rct_growth_ratio"] *= 2.2
    out["re_growth_ratio"] *= 1.9

    out["ohmic_r_norm"] *= 2.0

    return out


def inject_charge_interruption(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create an incomplete charging problem.

    Represents:
    - Charger failure
    - Loose connection
    - Charging stopped early
    """

    out = df.copy()

    out["total_charge_frac"] *= 0.55
    out["cv_capacity_frac"] *= 0.10

    out["cc_time_fraction"] = np.minimum(
        1.0,
        out["cc_time_fraction"] * 1.35
    )

    out["cc_cv_ah_ratio"] *= 6.0
    out["v_norm_at_cc_end"] *= 0.90

    return out


def inject_deep_discharge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a deep discharge problem.

    Represents:
    - BMS cutoff failure
    - Battery discharged below safe voltage
    """

    out = df.copy()

    out["audit_min_voltage_v"] = 1.75
    out["audit_min_v_norm"] = -0.44

    out["audit_dis_temp_max_c"] += 5.0

    return out


def inject_over_rate_charging(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create an over-current charging problem.

    Represents:
    - Wrong fast charger
    - Charging above recommended current
    """

    out = df.copy()

    out["mean_charge_c_rate"] *= 2.6

    out["ch_temp_max_c"] += 9.0
    out["ch_temp_rise_c"] += 7.0

    out["cc_capacity_frac"] *= 0.80

    return out


# Artificial faults used during validation.
FAULT_LIBRARY: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "thermal_runaway_precursor": inject_thermal_runaway_precursor,
    "resistance_fault": inject_resistance_fault,
    "charge_interruption": inject_charge_interruption,
    "deep_discharge": inject_deep_discharge,
    "over_rate_charging": inject_over_rate_charging,
}


def validate(
    df: pd.DataFrame,
    feature_set: str,
    seed: int = 42,
) -> Dict:
    """
    Test the anomaly detector using artificial faults.

    Since real battery fault labels are not available,
    normal battery cycles are modified to create fake faults.

    Checks:
    - How many faults were detected.
    - How many normal cycles were wrongly flagged.
    """

    detector = AnomalyDetector(feature_set=feature_set)

    # Train the detector using normal battery data.
    detector.fit(df)

    results = {
        "faults_tested": 0,
        "faults_detected": 0,
        "per_fault": {},
        "false_alarm_rate": 0.0,
    }

    # ------------------------------------------------------------
    # Test artificial faults
    # ------------------------------------------------------------

    for fault_name, injector in FAULT_LIBRARY.items():

        detected = 0
        tested = 0

        # Pick normal cycles and modify them into faults.
        sample = df.sample(
            n=min(20, len(df)),
            random_state=seed,
        )

        for _, row in sample.iterrows():

            cycle = pd.DataFrame([row])

            # Add artificial fault.
            faulty_cycle = injector(cycle)

            # Run anomaly detection.
            result = detector.detect_single(faulty_cycle.iloc[0])

            tested += 1

            if result.is_anomalous or result.score >= 50:
                detected += 1

        recall = detected / tested if tested else 0.0

        results["faults_tested"] += tested
        results["faults_detected"] += detected

        results["per_fault"][fault_name] = {
            "tested": tested,
            "detected": detected,
            "recall": recall,
        }

        logger.info(
            "  %-30s recall %.0f%% (%d/%d)",
            fault_name,
            recall * 100,
            detected,
            tested,
        )

    # ------------------------------------------------------------
    # Check false alarms
    # ------------------------------------------------------------
    #
    # Normal battery ageing should not be marked as a fault.

    false_alarms = 0

    normal_sample = df.sample(
        n=min(100, len(df)),
        random_state=seed,
    )

    for _, row in normal_sample.iterrows():

        result = detector.detect_single(row)

        if result.is_anomalous:
            false_alarms += 1

    results["false_alarm_rate"] = (
        false_alarms / len(normal_sample)
        if len(normal_sample)
        else 0.0
    )

    logger.info(
        "  False alarm rate: %.1f%% (%d/%d)",
        results["false_alarm_rate"] * 100,
        false_alarms,
        len(normal_sample),
    )

    return results


def main(argv=None) -> int:
    """
    Train the anomaly detector and save the model.
    """

    parser = argparse.ArgumentParser(
        description="Train the battery anomaly detector."
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=CYCLES_PATH,
        help="Path to feature dataset"
    )

    parser.add_argument(
        "--models",
        type=Path,
        default=MODELS_DIR,
        help="Directory to save models"
    )

    parser.add_argument(
        "--reports",
        type=Path,
        default=REPORTS_DIR,
        help="Directory to save reports"
    )

    parser.add_argument(
        "--feature-set",
        default="full",
        choices=list(FEATURE_SETS),
        help="Features used for anomaly detection"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args(argv)

    # ------------------------------------------------------------
    # Load dataset
    # ------------------------------------------------------------

    if not args.data.exists():

        logger.error(
            "Dataset not found: %s. Run build_dataset.py first.",
            args.data,
        )

        return 1

    df = pd.read_csv(
        args.data,
        parse_dates=["timestamp"],
    )

    logger.info(
        "Loaded %d cycles from %d batteries",
        len(df),
        df["battery_id"].nunique(),
    )

    args.models.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.reports.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------
    # Train detector
    # ------------------------------------------------------------

    logger.info("=" * 70)

    logger.info(
        "Training anomaly detector (%s feature set)",
        args.feature_set,
    )

    logger.info("=" * 70)

    detector = AnomalyDetector(
        feature_set=args.feature_set
    )

    detector.fit(df)

    # ------------------------------------------------------------
    # Validate detector
    # ------------------------------------------------------------

    logger.info(
        "Running synthetic fault validation..."
    )

    validation = validate(
        df,
        args.feature_set,
        seed=args.seed,
    )

    # Save validation results inside metadata.
    detector.metadata["validation"] = validation

    # ------------------------------------------------------------
    # Save model
    # ------------------------------------------------------------

    model_path = detector.save(
        args.models
    )

    logger.info(
        "Saved anomaly detector to %s",
        model_path,
    )

    # ------------------------------------------------------------
    # Save training report
    # ------------------------------------------------------------

    report = {
        "feature_set": args.feature_set,

        "dataset": {
            "cycles": int(len(df)),
            "batteries": int(df["battery_id"].nunique()),
        },

        "features": FEATURE_SETS[args.feature_set],

        "validation": validation,
    }

    report_path = (
        args.reports /
        "anomaly_training_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            report,
            fh,
            indent=2,
            default=str,
        )

    logger.info(
        "Saved training report to %s",
        report_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
