"""
Stage 2: Train and check the SOH model.

Example:

    python -m backend.batris.train_soh

This script:
1. Loads the feature dataset.
2. Trains the SOH models.
3. Tests the models using leave-one-battery-out (LOBO) validation.
4. Compares this with a random split for reference.
5. Calibrates the prediction interval.
6. Saves the trained model and training report.
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
from sklearn.model_selection import train_test_split

from .models.soh import (
    VARIANTS,
    SOHModel,
    features_for_variant
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("train_soh")


def _metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> Dict[str, float]:
    """Calculate the main model accuracy metrics."""

    # Difference between predicted and actual SOH.
    err = y_pred - y_true

    return {
        # Average prediction error.
        "mae": float(
            mean_absolute_error(
                y_true,
                y_pred
            )
        ),

        # Root mean squared error.
        "rmse": float(
            np.sqrt(
                np.mean(err ** 2)
            )
        ),

        # How well the predictions explain the actual values.
        "r2": float(
            r2_score(
                y_true,
                y_pred
            )
        ),

        # Largest absolute prediction error.
        "max_abs_error": float(
            np.max(
                np.abs(err)
            )
        ),

        # Average signed error.
        "bias": float(
            np.mean(err)
        ),

        # Convert MAE from SOH fraction to percentage points.
        "mae_soh_percentage_points": float(
            100 *
            mean_absolute_error(
                y_true,
                y_pred
            )
        ),
    }


def leave_one_battery_out(
    df: pd.DataFrame,
    variant: str
) -> Dict:
    """Train using all but one battery and test on the left-out battery."""

    # Get all battery IDs.
    batteries = sorted(
        df["battery_id"].unique()
    )

    per_battery: Dict[str, Dict] = {}

    pooled_true: List[float] = []
    pooled_pred: List[float] = []

    # Used later to calibrate the prediction interval.
    residual_ratios: List[float] = []

    coverage_hits = 0
    coverage_total = 0

    # Use each battery as the test battery once.
    for held_out in batteries:

        # Everything except the current battery is training data.
        train_df = df[
            df["battery_id"] != held_out
        ]

        # The held-out battery is the test data.
        test_df = df[
            df["battery_id"] == held_out
        ]

        # Train the model.
        model = (
            SOHModel(
                variant=variant
            )
            .fit(train_df)
        )

        # Get actual SOH values.
        y_true = (
            test_df["soh"]
            .to_numpy()
        )

        # Predict SOH for the unseen battery.
        y_pred = model.predict(
            test_df
        )

        # Get the uncalibrated prediction interval.
        interval = model.predict_interval(
            test_df,
            calibrated=False
        )

        # Check how many actual values are inside
        # the predicted interval.
        inside = (
            (y_true >= interval[:, 0]) &
            (y_true <= interval[:, 2])
        )

        coverage_hits += int(
            inside.sum()
        )

        coverage_total += len(
            inside
        )

        # Measure how far the actual values are from
        # the predicted interval centre.
        centre = interval[:, 1]

        half_width = np.where(
            y_true >= centre,
            interval[:, 2] - centre,
            centre - interval[:, 0]
        )

        with np.errstate(
            divide="ignore",
            invalid="ignore"
        ):
            residual_ratios.extend(
                (
                    np.abs(
                        y_true - centre
                    )
                    /
                    np.maximum(
                        half_width,
                        1e-6
                    )
                ).tolist()
            )

        # Calculate accuracy for this battery.
        stats = _metrics(
            y_true,
            y_pred
        )

        stats["n_cycles"] = int(
            len(y_true)
        )

        stats["interval_coverage"] = float(
            inside.mean()
        )

        per_battery[
            held_out
        ] = stats

        # Add this battery's values to the overall results.
        pooled_true.extend(
            y_true.tolist()
        )

        pooled_pred.extend(
            y_pred.tolist()
        )

        logger.info(
            "  hold out %-7s n=%3d  MAE=%.4f (%.2f pp)  RMSE=%.4f  R2=%+.3f  PI cov=%.0f%%",
            held_out,
            stats["n_cycles"],
            stats["mae"],
            stats["mae_soh_percentage_points"],
            stats["rmse"],
            stats["r2"],
            100 *
            stats["interval_coverage"],
        )

    # Calculate metrics across all held-out batteries together.
    pooled = _metrics(
        np.array(pooled_true),
        np.array(pooled_pred)
    )

    pooled[
        "interval_coverage_uncalibrated"
    ] = (
        coverage_hits /
        coverage_total
        if coverage_total
        else float("nan")
    )

    return {
        "per_battery": per_battery,
        "pooled": pooled,
        "residual_ratios": residual_ratios,
    }


def random_split_baseline(
    df: pd.DataFrame,
    variant: str
) -> Dict:
    """Use a random train/test split only as a comparison."""

    # Randomly divide the cycles into training and testing data.
    train_df, test_df = train_test_split(
        df,
        test_size=0.2,
        random_state=42,
        shuffle=True
    )

    # Train on the random training set.
    model = (
        SOHModel(
            variant=variant
        )
        .fit(train_df)
    )

    # Calculate the test metrics.
    return _metrics(
        test_df["soh"].to_numpy(),
        model.predict(test_df)
    )


def main(argv=None) -> int:

    # Set up command-line arguments.
    parser = argparse.ArgumentParser(
        description="Train the SOH estimator."
    )

    # Input feature table.
    parser.add_argument(
        "--data",
        type=Path,
        default=CYCLES_PATH
    )

    # Folder for trained models.
    parser.add_argument(
        "--models",
        type=Path,
        default=MODELS_DIR
    )

    # Folder for reports.
    parser.add_argument(
        "--reports",
        type=Path,
        default=REPORTS_DIR
    )

    # Choose which model variants to train.
    parser.add_argument(
        "--variants",
        nargs="+",
        default=list(VARIANTS),
        choices=list(VARIANTS)
    )

    # Option to skip validation.
    parser.add_argument(
        "--skip-cv",
        action="store_true",
        help="Skip cross-validation and just fit final models"
    )

    args = parser.parse_args(argv)

    # Make sure the feature table exists.
    if not args.data.exists():
        logger.error(
            "Feature table %s not found. Run: "
            "python -m backend.batris.build_dataset",
            args.data
        )
        return 1

    # Load the feature table.
    df = pd.read_csv(
        args.data,
        parse_dates=["timestamp"]
    )

    # Keep only rows with a valid SOH value.
    df = df[
        np.isfinite(df["soh"])
    ].reset_index(drop=True)

    logger.info(
        "Loaded %d cycles from %d batteries",
        len(df),
        df["battery_id"].nunique()
    )

    # Create output folders.
    args.models.mkdir(
        parents=True,
        exist_ok=True
    )

    args.reports.mkdir(
        parents=True,
        exist_ok=True
    )

    # Basic information for the final report.
    report: Dict = {
        "n_cycles": int(len(df)),
        "batteries":
            sorted(
                df["battery_id"]
                .unique()
                .tolist()
        ),
        "variants": {}
    }

    # Train every requested model variant.
    for variant in args.variants:

        features = features_for_variant(
            variant
        )

        logger.info(
            "=" * 72
        )

        logger.info(
            "VARIANT: %s  (%d features)",
            variant,
            len(features)
        )

        if variant == "provenance_free":
            logger.info(
                "  history, baseline and protocol-dependent features excluded"
            )

            logger.info(
                "  -> grades a battery from present physical condition alone"
            )

        logger.info(
            "=" * 72
        )

        entry: Dict = {
            "n_features":
                len(features),
            "features":
                features
        }

        residual_ratios: List[float] = []

        # Run cross-validation unless the user asked to skip it.
        if not args.skip_cv:

            logger.info(
                "Leave-one-battery-out cross-validation:"
            )

            cv = leave_one_battery_out(
                df,
                variant
            )

            # Save the values needed for interval calibration.
            residual_ratios = cv.pop(
                "residual_ratios"
            )

            entry["lobo"] = cv

            pooled = cv["pooled"]

            logger.info(
                "  POOLED LOBO   MAE=%.4f (%.2f SOH points)  RMSE=%.4f  R2=%+.3f",
                pooled["mae"],
                pooled["mae_soh_percentage_points"],
                pooled["rmse"],
                pooled["r2"],
            )

            # Also calculate the easier random split.
            baseline = random_split_baseline(
                df,
                variant
            )

            entry[
                "random_split_baseline"
            ] = baseline

            logger.info(
                "  Random-split (OPTIMISTIC, shown for contrast only)  "
                "MAE=%.4f  R2=%+.3f",
                baseline["mae"],
                baseline["r2"],
            )

            # Show how much better the random split looks.
            logger.info(
                "    -> the random split looks %.1fx better than LOBO. "
                "That gap is leakage between adjacent cycles, not skill.",
                pooled["mae"] /
                baseline["mae"]
                if baseline["mae"]
                else float("nan"),
            )

        # Train the final model using all available batteries.
        logger.info(
            "Fitting final %s model on all %d cycles...",
            variant,
            len(df)
        )

        model = (
            SOHModel(
                variant=variant
            )
            .fit(df)
        )

        # Calibrate the prediction interval using
        # the held-out validation errors.
        if residual_ratios:

            factor = model.calibrate(
                np.array(
                    residual_ratios
                ),
                target_coverage=0.90
            )

            model.metadata[
                "interval_calibration_factor"
            ] = factor

            model.metadata[
                "interval_calibration_basis"
            ] = (
                "leave-one-battery-out residuals"
            )

            # Check how much validation data is covered
            # after calibration.
            achieved = float(
                np.mean(
                    np.array(
                        residual_ratios
                    ) <= factor
                )
            )

            entry[
                "interval_calibration"
            ] = {
                "factor": factor,
                "coverage_before":
                    pooled[
                        "interval_coverage_uncalibrated"
                    ],
                "coverage_after":
                    achieved,
            }

            logger.info(
                "  Interval calibration: raw 90%% interval covered %.0f%% "
                "of held-out points; widening by %.2fx brings coverage to %.0f%%.",
                100 *
                pooled[
                    "interval_coverage_uncalibrated"
                ],
                factor,
                100 *
                achieved,
            )

            # Save the validation results inside the model metadata.
            model.metadata[
                "validation"
            ] = {
                "method":
                    "leave-one-battery-out cross-validation",

                "mae_soh_percentage_points":
                    round(
                        pooled[
                            "mae_soh_percentage_points"
                        ],
                        2
                    ),

                "rmse":
                    round(
                        pooled["rmse"],
                        4
                    ),

                "r2":
                    round(
                        pooled["r2"],
                        3
                    ),

                "n_batteries":
                    len(
                        cv["per_battery"]
                    ),

                "worst_battery_mae_soh_points":
                    round(
                        100 *
                        max(
                            v["mae"]
                            for v
                            in cv[
                                "per_battery"
                            ].values()
                        ),
                        2
                    ),
            }

        # Save the trained model.
        model.save(args.models)

        # Get overall feature importance.
        importance = (model.feature_importance())

        entry[
            "feature_importance"
        ] = {
            k: round(
                float(v),
                5
            )
            for k, v
            in importance.items()
        }

        entry[
            "metadata"
        ] = model.metadata

        logger.info(
            "  Top predictive features:"
        )

        for name, gain in (
            importance.head(8).items()
        ):
            logger.info(
                "    %-26s %5.1f%%",
                name,
                100 * gain
            )

        report[
            "variants"
        ][variant] = entry

    # Save the complete training report.
    report_path = (
        args.reports /
        "soh_training_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as fh:

        json.dump(
            report,
            fh,
            indent=2,
            default=str
        )

    logger.info(
        "=" * 72
    )

    logger.info(
        "Wrote training report to %s",
        report_path
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
