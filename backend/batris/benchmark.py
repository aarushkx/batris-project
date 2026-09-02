"""
Model Benchmark: compare candidate SOH models under the same LOBO protocol.

    python -m backend.batris.benchmark

Trains six models, evaluates each via leave-one-battery-out cross-validation,
and writes:
  - generated/reports/benchmark_results.json
  - generated/plots/benchmark_lobo_mae.png
  - generated/plots/benchmark_per_battery_mae.png
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from .features import SOH_FEATURES
from .models.soh import DEFAULT_PARAMS
from .paths import CYCLES_PATH, PLOTS_DIR, REPORTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")


# ---------------------------------------------------------------------------
# Mean-baseline estimator (scikit-learn compatible)
# ---------------------------------------------------------------------------

class MeanBaseline(BaseEstimator, RegressorMixin):
    """Predicts the training-set mean for every sample."""

    def __init__(self) -> None:
        self.mean_: float = 0.0

    def fit(self, X: Any, y: Any) -> "MeanBaseline":
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X: Any) -> np.ndarray:
        return np.full(len(X), self.mean_)


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

def _build_models() -> List[Tuple[str, str, Any]]:
    """Return (key, display_name, estimator) triples."""
    import xgboost as xgb

    return [
        (
            "mean_baseline",
            "Mean Baseline",
            MeanBaseline(),
        ),
        (
            "linear_regression",
            "Linear Regression",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("lr", LinearRegression()),
            ]),
        ),
        (
            "random_forest",
            "Random Forest",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("rf", RandomForestRegressor(
                    n_estimators=300,
                    max_depth=6,
                    min_samples_leaf=5,
                    random_state=42,
                    n_jobs=4,
                )),
            ]),
        ),
        (
            "gradient_boosting",
            "Gradient Boosting",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("gb", GradientBoostingRegressor(
                    n_estimators=400,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.85,
                    min_samples_leaf=5,
                    random_state=42,
                )),
            ]),
        ),
        (
            "svr",
            "SVR",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("svr", SVR(kernel="rbf", C=10.0, epsilon=0.01)),
            ]),
        ),
        (
            "xgboost",
            "XGBoost",
            xgb.XGBRegressor(
                objective="reg:squarederror",
                **DEFAULT_PARAMS,
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    err = y_pred - y_true
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "r2": float(r2_score(y_true, y_pred)),
        "max_abs_error": float(np.max(np.abs(err))),
        "bias": float(np.mean(err)),
        # Convenience: already in SOH percentage points
        "mae_soh_points": float(100 * mean_absolute_error(y_true, y_pred)),
        "rmse_soh_points": float(100 * np.sqrt(np.mean(err ** 2))),
        "max_error_soh_points": float(100 * np.max(np.abs(err))),
        "bias_soh_points": float(100 * np.mean(err)),
    }


# ---------------------------------------------------------------------------
# LOBO benchmark
# ---------------------------------------------------------------------------

def run_benchmark(
    df: pd.DataFrame,
    features: List[str],
) -> Dict[str, Any]:
    """Run all candidate models through leave-one-battery-out evaluation."""

    batteries = sorted(df["battery_id"].unique())
    models = _build_models()

    results: List[Dict[str, Any]] = []

    for model_key, display_name, estimator in models:
        logger.info("Evaluating %s ...", display_name)

        per_battery: Dict[str, Dict] = {}
        trajectories: Dict[str, Dict[str, List[float]]] = {}
        pooled_true: List[float] = []
        pooled_pred: List[float] = []

        for held_out in batteries:
            train = df[df["battery_id"] != held_out]
            # Sort the held-out fold by cycle so the stored trajectory is
            # already in cycle order — the frontend plots it as-is.
            test = df[df["battery_id"] == held_out].sort_values("cycle_index")

            X_train = train[features].to_numpy()
            y_train = train["soh"].to_numpy()
            X_test = test[features].to_numpy()
            y_test = test["soh"].to_numpy()

            # Clone the estimator for a fresh fit each fold
            from sklearn.base import clone
            est = clone(estimator)
            est.fit(X_train, y_train)

            y_pred = est.predict(X_test)

            per_battery[held_out] = _metrics(y_test, y_pred)
            trajectories[held_out] = {
                "cycle_index": test["cycle_index"].astype(int).tolist(),
                "measured_soh": y_test.tolist(),
                "estimated_soh": y_pred.tolist(),
            }

            pooled_true.extend(y_test.tolist())
            pooled_pred.extend(y_pred.tolist())

            logger.info(
                "  %s held out → MAE %.2f SOH pts",
                held_out,
                per_battery[held_out]["mae_soh_points"],
            )

        overall = _metrics(np.array(pooled_true), np.array(pooled_pred))

        results.append({
            "model_key": model_key,
            "model_display_name": display_name,
            "overall": overall,
            "per_battery": per_battery,
            "trajectories": trajectories,
        })

        logger.info(
            "  %s overall → MAE %.2f  RMSE %.2f  R² %.3f",
            display_name,
            overall["mae_soh_points"],
            overall["rmse_soh_points"],
            overall["r2"],
        )

    # Determine the best model
    best = min(results, key=lambda r: r["overall"]["mae_soh_points"])

    return {
        "n_cycles": len(df),
        "batteries": batteries,
        "n_batteries": len(batteries),
        "features_used": len(features),
        "models": results,
        "best_model": best["model_key"],
        "best_model_display_name": best["model_display_name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Plot generation
# ---------------------------------------------------------------------------

def make_benchmark_plots(
    results: Dict[str, Any],
    out_dir: Path,
) -> List[str]:
    """Generate comparison charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written: List[str] = []
    models = results["models"]
    batteries = results["batteries"]
    best_key = results["best_model"]

    # Colour palette — matches BATRIS design tokens (light mode)
    palette = ["#97a09b", "#5b6560", "#1f8a4c", "#b4740e", "#1b3fe0", "#6b4be0"]
    # Fallback if more models than colours
    while len(palette) < len(models):
        palette.append("#5b6560")

    # ---- 1. Overall LOBO MAE bar chart ----
    fig, ax = plt.subplots(figsize=(10, 5.5))
    names = [m["model_display_name"] for m in models]
    maes = [m["overall"]["mae_soh_points"] for m in models]
    bars_colors = []
    for i, m in enumerate(models):
        if m["model_key"] == best_key:
            bars_colors.append("#1b3fe0")
        else:
            bars_colors.append("#97a09b")

    bars = ax.barh(names[::-1], maes[::-1], color=bars_colors[::-1], height=0.55)
    ax.set_xlabel("LOBO MAE (SOH percentage points) — lower is better")
    ax.set_title(
        "Model Comparison — Leave-One-Battery-Out MAE\n"
        f"{results['n_batteries']} batteries, {results['n_cycles']} cycles, {results['features_used']} features",
        fontsize=11,
    )
    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)

    # Value labels
    for bar, val in zip(bars, maes[::-1]):
        ax.text(
            bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}", va="center", fontsize=9, fontweight="bold",
        )

    ax.set_xlim(0, max(maes) * 1.25)
    fig.tight_layout()
    fig.savefig(out_dir / "benchmark_lobo_mae.png", dpi=140)
    plt.close(fig)
    written.append("benchmark_lobo_mae.png")

    # ---- 2. Per-battery MAE grouped bar chart ----
    n_models = len(models)
    n_bats = len(batteries)
    x = np.arange(n_bats)
    width = 0.12
    offset = np.linspace(-(n_models - 1) / 2 * width, (n_models - 1) / 2 * width, n_models)

    fig, ax = plt.subplots(figsize=(12, 5.5))
    for i, m in enumerate(models):
        vals = [m["per_battery"][b]["mae_soh_points"] for b in batteries]
        ax.bar(
            x + offset[i], vals, width * 0.90,
            label=m["model_display_name"],
            color=palette[i],
            alpha=0.88,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(batteries, fontsize=10)
    ax.set_ylabel("MAE (SOH percentage points)")
    ax.set_title(
        "Per-Battery MAE — How Each Model Generalises to Unseen Batteries",
        fontsize=11,
    )
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out_dir / "benchmark_per_battery_mae.png", dpi=140)
    plt.close(fig)
    written.append("benchmark_per_battery_mae.png")

    logger.info("Wrote %d benchmark plots to %s", len(written), out_dir)
    return written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the BATRIS model benchmark."
    )
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
    parser.add_argument("--plots", type=Path, default=PLOTS_DIR)
    parser.add_argument("--skip-plots", action="store_true")
    args = parser.parse_args(argv)

    if not args.data.exists():
        logger.error(
            "Missing %s. Run:  python -m backend.batris.build_dataset",
            args.data,
        )
        return 1

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df[np.isfinite(df["soh"])].reset_index(drop=True)

    logger.info(
        "Loaded %d cycles from %d batteries",
        len(df), df["battery_id"].nunique(),
    )

    args.reports.mkdir(parents=True, exist_ok=True)
    args.plots.mkdir(parents=True, exist_ok=True)

    # Run the benchmark
    results = run_benchmark(df, SOH_FEATURES)

    # Save results
    report_path = args.reports / "benchmark_results.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    logger.info("Wrote benchmark results to %s", report_path)

    # Generate plots
    if not args.skip_plots:
        make_benchmark_plots(results, args.plots)

    # Print summary table
    logger.info("")
    logger.info("=" * 80)
    logger.info("BENCHMARK SUMMARY")
    logger.info("=" * 80)
    logger.info(
        "%-22s %8s %8s %8s %10s %8s",
        "Model", "MAE↓", "RMSE↓", "R²↑", "MaxErr↓", "Bias",
    )
    logger.info("-" * 80)
    for m in results["models"]:
        o = m["overall"]
        marker = " ◀ BEST" if m["model_key"] == results["best_model"] else ""
        logger.info(
            "%-22s %7.2f %7.2f %7.3f %9.2f %+7.2f%s",
            m["model_display_name"],
            o["mae_soh_points"],
            o["rmse_soh_points"],
            o["r2"],
            o["max_error_soh_points"],
            o["bias_soh_points"],
            marker,
        )
    logger.info("=" * 80)
    logger.info(
        "Best model: %s (LOBO MAE = %.2f SOH points)",
        results["best_model_display_name"],
        min(m["overall"]["mae_soh_points"] for m in results["models"]),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
