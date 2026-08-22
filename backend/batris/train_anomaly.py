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
from typing import Callable, Dict, List

import numpy as np
import pandas as pd

from .models.anomaly import ANOMALY_FEATURES, FEATURE_SETS, AnomalyDetector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_anomaly")


# ===========================================================================
# Synthetic fault signatures
# ===========================================================================
# Creates artificial battery faults by modifying normal cycles.
# The changes are based on real battery failure patterns and are kept realistic
# so the model learns meaningful fault behaviour.

def inject_thermal_runaway_precursor(df: pd.DataFrame) -> pd.DataFrame:
    """Simulates cooling failure or internal problems where the battery
    temperature becomes much higher than expected during charging."""
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
    """Simulates resistance increase caused by issues like interconnect damage
    or electrode degradation while the battery capacity remains similar."""
    out = df.copy()
    out["rct_norm"] *= 2.2
    out["re_norm"] *= 1.9
    out["rct_growth_ratio"] *= 2.2
    out["re_growth_ratio"] *= 1.9
    out["ohmic_r_norm"] *= 2.0
    return out


def inject_charge_interruption(df: pd.DataFrame) -> pd.DataFrame:
    """Simulates charger problems where charging stops early and the battery
    does not reach full charge."""
    out = df.copy()
    out["total_charge_frac"] *= 0.55
    out["cv_capacity_frac"] *= 0.10
    out["cc_time_fraction"] = np.minimum(1.0, out["cc_time_fraction"] * 1.35)
    out["cc_cv_ah_ratio"] *= 6.0
    out["v_norm_at_cc_end"] *= 0.90
    return out


def inject_deep_discharge(df: pd.DataFrame) -> pd.DataFrame:
    """Simulates BMS cutoff failure where the battery is discharged below its
    safe voltage limit.

    The voltage is set low enough to represent actual damage instead of a normal
    deep discharge warning.
    """
    out = df.copy()
    out["audit_min_voltage_v"] = 1.75
    out["audit_min_v_norm"] = -0.44
    out["audit_dis_temp_max_c"] += 5.0
    return out


def inject_over_rate_charging(df: pd.DataFrame) -> pd.DataFrame:
    """Simulates a faulty fast charger that charges the battery above its
    recommended C-rate limit.
    """
    out = df.copy()
    out["mean_charge_c_rate"] *= 2.6
    out["ch_temp_max_c"] += 9.0
    out["ch_temp_rise_c"] += 7.0
    out["cc_capacity_frac"] *= 0.80
    return out


FAULT_LIBRARY: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "thermal_runaway_precursor": inject_thermal_runaway_precursor,
    "resistance_fault": inject_resistance_fault,
    "charge_interruption": inject_charge_interruption,
    "deep_discharge": inject_deep_discharge,
    "over_rate_charging": inject_over_rate_charging,
}


def validate(detector: AnomalyDetector, df: pd.DataFrame,
             n_samples: int = 60, seed: int = 42) -> Dict:
    """Measures how well the model detects injected faults.

    Faults are added to some cycles inside normal battery history and the complete
    history is tested. This keeps the battery's normal context, which is important
    for detecting changes based on recent behaviour.
    """
    rng = np.random.default_rng(seed)

    clean_results = detector.detect(df)
    false_alarms = sum(r.is_anomalous for r in clean_results)
    false_alarm_rate = false_alarms / len(clean_results)

    logger.info("Clean data: %d of %d cycles flagged (%.1f%% false-alarm rate)",
                false_alarms, len(clean_results), 100 * false_alarm_rate)
    logger.info("Injected fault recall (faults embedded in intact history):")

    per_fault: Dict[str, Dict] = {}
    for name, injector in FAULT_LIBRARY.items():
        # Choose target cycles late enough that a rolling context exists.
        eligible = np.flatnonzero(df["cycle_index"].to_numpy() > 12)
        targets = rng.choice(eligible, size=min(
            n_samples, len(eligible)), replace=False)

        faulted_df = df.copy()
        faulted_df.loc[df.index[targets]] = injector(
            df.iloc[targets]
        ).to_numpy()
        faulted_df = faulted_df.astype(df.dtypes.to_dict())

        results = detector.detect(faulted_df)
        injected = [results[i] for i in targets]

        detected = sum(r.is_anomalous for r in injected)
        recall = detected / len(injected)
        sources = [a.source for r in injected for a in r.anomalies]
        critical = sum(r.max_severity == "critical" for r in injected)

        per_fault[name] = {
            "n_injected": int(len(injected)),
            "recall": float(recall),
            "critical_rate": float(critical / len(injected)),
            "mean_score": float(np.mean([r.score for r in injected])),
            "detected_by": {
                src: sources.count(src) for src in ("rule", "statistical", "trajectory")
            },
        }
        logger.info("  %-28s recall=%5.1f%%  critical=%5.1f%%  mean score=%4.1f",
                    name, 100 * recall, 100 * per_fault[name]["critical_rate"],
                    per_fault[name]["mean_score"])

    mean_recall = float(np.mean([v["recall"] for v in per_fault.values()]))
    logger.info("  %-28s %5.1f%%", "MEAN RECALL", 100 * mean_recall)

    return {
        "false_alarm_rate": float(false_alarm_rate),
        "n_clean_cycles": int(len(clean_results)),
        "mean_recall": mean_recall,
        "per_fault": per_fault,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Train the anomaly detector.")
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--models", type=Path, default=MODELS_DIR)
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
    parser.add_argument("--contamination", type=float, default=0.02,
                        help="Expected fraction of abnormal cycles in training data")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args(argv)

    if not args.data.exists():
        logger.error("Feature table %s not found. Run:  python -m backend.batris.build_dataset",
                     args.data)
        return 1

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df.sort_values(["battery_id", "cycle_index"]).reset_index(drop=True)
    logger.info("Loaded %d cycles from %d batteries",
                len(df), df["battery_id"].nunique())

    missing = [f for f in ANOMALY_FEATURES if f not in df.columns]
    if missing:
        logger.error("Feature table is missing columns: %s", missing)
        return 1

    detector = AnomalyDetector(contamination=args.contamination).fit(df)

    # A second detector using only charge-side features, for assessing an
    # unknown battery from a single uploaded charge cycle where no discharge
    # record exists. See CHARGE_ANOMALY_FEATURES for why this is trained
    # separately rather than imputed.
    charge_detector = AnomalyDetector(
        contamination=args.contamination, feature_set="charge_only"
    ).fit(df)
    charge_detector.save(args.models)
    logger.info("Charge-only detector: %d features, threshold %.5f",
                len(charge_detector.features), charge_detector.score_threshold)

    report: Dict = {"metadata": detector.metadata,
                    "charge_only_metadata": charge_detector.metadata}
    if not args.skip_validation:
        logger.info("=" * 72)
        logger.info("VALIDATION BY SYNTHETIC FAULT INJECTION")
        logger.info("=" * 72)
        report["validation"] = validate(detector, df)

    args.models.mkdir(parents=True, exist_ok=True)
    args.reports.mkdir(parents=True, exist_ok=True)
    detector.save(args.models)
    with open(args.reports / "anomaly_training_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    logger.info("Wrote report to %s", args.reports /
                "anomaly_training_report.json")

   # Displays battery cycles that the detector identifies as abnormal.
    # These are actual unusual cases from the dataset, not random errors.
    results = detector.detect(df)
    flagged = [(df.iloc[i]["battery_id"], int(df.iloc[i]["cycle_index"]),
                r.score, r.max_severity, [a.code for a in r.anomalies])
               for i, r in enumerate(results) if r.is_anomalous]
    if flagged:
        logger.info("-" * 72)
        logger.info("Real cycles flagged in this dataset (%d of %d):",
                    len(flagged), len(results))
        for battery, cycle, score, severity, codes in flagged[:15]:
            logger.info("  %-7s cycle %3d  score=%5.1f  %-8s  %s",
                        battery, cycle, score, severity, ", ".join(codes))
        if len(flagged) > 15:
            logger.info("  ... and %d more", len(flagged) - 15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
