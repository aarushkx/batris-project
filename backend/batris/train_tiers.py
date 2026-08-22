"""
Stage 2b: Train separate SOH models for each input tier.

Each tier has its own model, validation process and uncertainty calculation.
This ensures that each model is tested using the same type of data it will
receive during actual use.

A single model with missing values was avoided because it could give confident
predictions on inputs it was never trained on.
"""

from __future__ import annotations

from .paths import CYCLES_PATH, MODELS_DIR, REPORTS_DIR

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from .models.soh import SOHModel
from .tiers import TIER_ORDER, get_tier

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_tiers")


def validate_tier(df: pd.DataFrame, features: List[str]) -> Dict:
    """Leave-one-battery-out validation for one tier's feature set."""
    pooled_true: List[float] = []
    pooled_pred: List[float] = []
    residual_ratios: List[float] = []
    per_battery: Dict[str, Dict] = {}

    for held_out in sorted(df["battery_id"].unique()):
        train = df[df["battery_id"] != held_out]
        test = df[df["battery_id"] == held_out]

        model = SOHModel(variant="full")
        model.features = list(features)  # tier feature set
        model.fit(train)

        y_true = test["soh"].to_numpy()
        y_pred = model.predict(test)
        interval = model.predict_interval(test, calibrated=False)

        centre = interval[:, 1]
        half = np.where(y_true >= centre,
                        interval[:, 2] - centre, centre - interval[:, 0])
        residual_ratios.extend(
            (np.abs(y_true - centre) / np.maximum(half, 1e-6)).tolist()
        )

        per_battery[held_out] = {
            "n_cycles": int(len(y_true)),
            "mae_soh_points": round(100 * mean_absolute_error(y_true, y_pred), 3),
            "r2": round(float(r2_score(y_true, y_pred)), 4),
        }
        pooled_true.extend(y_true.tolist())
        pooled_pred.extend(y_pred.tolist())

    mae = mean_absolute_error(pooled_true, pooled_pred)
    return {
        "per_battery": per_battery,
        "mae": float(mae),
        "mae_soh_points": round(100 * mae, 3),
        "rmse": round(float(np.sqrt(np.mean(
            (np.array(pooled_pred) - np.array(pooled_true)) ** 2))), 4),
        "r2": round(float(r2_score(pooled_true, pooled_pred)), 4),
        "worst_battery_mae_soh_points": round(
            max(v["mae_soh_points"] for v in per_battery.values()), 3
        ),
        "residual_ratios": residual_ratios,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Train one SOH model per user input tier."
    )
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--models", type=Path, default=MODELS_DIR)
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
    args = parser.parse_args(argv)

    if not args.data.exists():
        logger.error(
            "Missing %s. Run:  python -m backend.batris.build_dataset", args.data)
        return 1

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df[np.isfinite(df["soh"])].reset_index(drop=True)
    args.models.mkdir(parents=True, exist_ok=True)
    args.reports.mkdir(parents=True, exist_ok=True)

    logger.info("Training %d tier models on %d cycles from %d batteries",
                len(TIER_ORDER), len(df), df["battery_id"].nunique())

    report: Dict = {"tiers": {}}

    for tier_key in TIER_ORDER:
        tier = get_tier(tier_key)
        logger.info("=" * 72)
        logger.info("TIER %d: %s  (%d features, source=%s)",
                    tier.rank, tier.display_name, len(tier.features), tier.source)

        validation = validate_tier(df, tier.features)
        residual_ratios = validation.pop("residual_ratios")

        for battery, stats in validation["per_battery"].items():
            logger.info("  hold out %-7s MAE=%5.2f SOH points  R2=%+.3f",
                        battery, stats["mae_soh_points"], stats["r2"])
        logger.info("  POOLED  MAE=%5.2f SOH points  RMSE=%.4f  R2=%+.3f  worst cell %.2f",
                    validation["mae_soh_points"], validation["rmse"],
                    validation["r2"], validation["worst_battery_mae_soh_points"])

        if not tier.reliable:
            logger.info("  -> marked INDICATIVE ONLY; no reuse grade is issued "
                        "from this tier.")

        # Final model on all cells, with intervals calibrated from held-out
        # residuals for this specific tier.
        model = SOHModel(variant="full")
        model.features = list(tier.features)
        model.fit(df)
        factor = model.calibrate(
            np.array(residual_ratios), target_coverage=0.90)

        model.metadata.update({
            "tier": tier_key,
            "tier_rank": tier.rank,
            "tier_display_name": tier.display_name,
            "tier_reliable": tier.reliable,
            "features": list(tier.features),
            "interval_calibration_factor": factor,
            "validation": {
                "method": "leave-one-battery-out cross-validation",
                "mae_soh_percentage_points": validation["mae_soh_points"],
                "rmse": validation["rmse"],
                "r2": validation["r2"],
                "worst_battery_mae_soh_points":
                    validation["worst_battery_mae_soh_points"],
                "n_batteries": len(validation["per_battery"]),
            },
        })
        model.variant = f"tier_{tier_key}"
        model.save(args.models)

        logger.info("  interval calibration factor %.2fx", factor)
        report["tiers"][tier_key] = {
            "display_name": tier.display_name,
            "rank": tier.rank,
            "n_features": len(tier.features),
            "features": list(tier.features),
            "reliable": tier.reliable,
            "validation": validation,
            "interval_calibration_factor": factor,
        }

    logger.info("=" * 72)
    logger.info("Summary (leave-one-battery-out):")
    for tier_key in TIER_ORDER:
        entry = report["tiers"][tier_key]
        flag = "" if entry["reliable"] else "   [INDICATIVE ONLY]"
        logger.info("  tier %d  %-38s %5.2f SOH points  R2 %+.3f%s",
                    entry["rank"], entry["display_name"][:38],
                    entry["validation"]["mae_soh_points"],
                    entry["validation"]["r2"], flag)

    path = args.reports / "tier_training_report.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
