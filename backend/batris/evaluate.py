# """
# Stage 4: Generate the complete evaluation report.

#     python -m backend.batris.evaluate

# Creates a Markdown report and diagnostic plots by combining:
# - SOH model validation results
# - Anomaly detection results
# - Feature importance analysis
# """

# from __future__ import annotations

# from .paths import CYCLES_PATH, PLOTS_DIR, REPORTS_DIR

# import argparse
# import json
# import logging
# import sys
# from pathlib import Path
# from typing import Dict, List

# import numpy as np
# import pandas as pd
# from sklearn.metrics import mean_absolute_error, r2_score

# from .features import FEATURE_GROUPS, SOH_FEATURES
# from .models.soh import DEFAULT_PARAMS, VARIANTS, SOHModel, features_for_variant

# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
#     datefmt="%H:%M:%S",
# )
# logger = logging.getLogger("evaluate")


# def lobo_predictions(df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
#     """Out-of-sample predictions for every cycle, via leave-one-battery-out."""
#     import xgboost as xgb

#     frames = []
#     for held_out in sorted(df["battery_id"].unique()):
#         train = df[df["battery_id"] != held_out]
#         test = df[df["battery_id"] == held_out].copy()
#         model = xgb.XGBRegressor(
#             objective="reg:squarederror", **DEFAULT_PARAMS)
#         model.fit(train[features], train["soh"])
#         test["soh_predicted"] = model.predict(test[features])
#         frames.append(test)
#     return pd.concat(frames, ignore_index=True)


# def ablation(df: pd.DataFrame) -> Dict[str, Dict]:
#     """Measures how much each feature group affects the model.

#     Feature importance can be misleading when features are related, so this checks
#     performance after removing each group to see which features are actually useful.
#     """
#     results: Dict[str, Dict] = {}

#     baseline = lobo_predictions(df, SOH_FEATURES)
#     base_mae = mean_absolute_error(baseline["soh"], baseline["soh_predicted"])
#     results["all_features"] = {
#         "n_features": len(SOH_FEATURES),
#         "mae": float(base_mae),
#         "mae_soh_points": round(100 * base_mae, 3),
#         "delta_vs_baseline": 0.0,
#     }

#     for group, members in FEATURE_GROUPS.items():
#         remaining = [f for f in SOH_FEATURES if f not in members]
#         if not remaining:
#             continue
#         preds = lobo_predictions(df, remaining)
#         mae = mean_absolute_error(preds["soh"], preds["soh_predicted"])
#         results[f"without_{group}"] = {
#             "n_features": len(remaining),
#             "mae": float(mae),
#             "mae_soh_points": round(100 * mae, 3),
#             "delta_vs_baseline": round(100 * (mae - base_mae), 3),
#         }
#         logger.info("  without %-22s MAE=%.4f (%+.3f SOH points vs all features)",
#                     group, mae, 100 * (mae - base_mae))

#     # Each group in isolation.
#     for group, members in FEATURE_GROUPS.items():
#         preds = lobo_predictions(df, members)
#         mae = mean_absolute_error(preds["soh"], preds["soh_predicted"])
#         results[f"only_{group}"] = {
#             "n_features": len(members),
#             "mae": float(mae),
#             "mae_soh_points": round(100 * mae, 3),
#             "delta_vs_baseline": round(100 * (mae - base_mae), 3),
#         }
#         logger.info("  only    %-22s MAE=%.4f", group, mae)

#     return results


# def make_plots(df: pd.DataFrame, out_dir: Path) -> List[str]:
#     """Diagnostic figures. Returns the filenames written."""
#     import matplotlib
#     matplotlib.use("Agg")
#     import matplotlib.pyplot as plt

#     written: List[str] = []
#     preds = lobo_predictions(df, SOH_FEATURES)

#     # 1. Degradation trajectories: estimated vs measured, per battery.
#     batteries = sorted(df["battery_id"].unique())
#     fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)
#     for ax, battery in zip(axes.ravel(), batteries):
#         subset = preds[preds["battery_id"] ==
#                        battery].sort_values("cycle_index")
#         ax.plot(subset["cycle_index"], 100 * subset["soh"],
#                 label="Measured (reference discharge)", linewidth=1.8, color="#1f77b4")
#         ax.plot(subset["cycle_index"], 100 * subset["soh_predicted"],
#                 label="Estimated (held-out model)", linewidth=1.4,
#                 color="#d62728", linestyle="--")
#         ax.axhline(80, color="grey", linestyle=":", linewidth=1)
#         ax.text(2, 80.6, "80% end of first life", fontsize=7, color="grey")
#         mae = mean_absolute_error(subset["soh"], subset["soh_predicted"])
#         ax.set_title(f"{battery}  (out-of-sample MAE {100 * mae:.2f} SOH points)",
#                      fontsize=10)
#         ax.set_xlabel("Cycle")
#         ax.set_ylabel("State of Health (%)")
#         ax.grid(alpha=0.3)
#     axes.ravel()[0].legend(fontsize=8)
#     fig.suptitle("SOH estimation, leave-one-battery-out\n"
#                  "each curve predicted by a model that never saw that cell",
#                  fontsize=12)
#     fig.tight_layout()
#     fig.savefig(out_dir / "soh_trajectories.png", dpi=130)
#     plt.close(fig)
#     written.append("soh_trajectories.png")

#     # 2. Parity plot with the leakage comparison.
#     from sklearn.model_selection import train_test_split
#     import xgboost as xgb
#     train, test = train_test_split(
#         df, test_size=0.2, random_state=42, shuffle=True)
#     leaky = xgb.XGBRegressor(objective="reg:squarederror", **DEFAULT_PARAMS)
#     leaky.fit(train[SOH_FEATURES], train["soh"])
#     leaky_pred = leaky.predict(test[SOH_FEATURES])

#     fig, axes = plt.subplots(1, 2, figsize=(11, 5))
#     for ax, (y_true, y_pred, title) in zip(axes, [
#         (preds["soh"], preds["soh_predicted"],
#          "Leave-one-battery-out\n(honest: model never saw this cell)"),
#         (test["soh"], leaky_pred,
#          "Random cycle split\n(optimistic: adjacent cycles leak)"),
#     ]):
#         ax.scatter(100 * np.asarray(y_true), 100 * np.asarray(y_pred),
#                    s=9, alpha=0.45, edgecolors="none")
#         lo, hi = 55, 105
#         ax.plot([lo, hi], [lo, hi], "k--", linewidth=1)
#         ax.set_xlim(lo, hi)
#         ax.set_ylim(lo, hi)
#         ax.set_xlabel("Measured SOH (%)")
#         ax.set_ylabel("Estimated SOH (%)")
#         ax.set_title(f"{title}\nMAE {100 * mean_absolute_error(y_true, y_pred):.2f} pts,"
#                      f" R2 {r2_score(y_true, y_pred):.3f}", fontsize=9)
#         ax.grid(alpha=0.3)
#     fig.suptitle("Why the validation method matters more than the model",
#                  fontsize=12)
#     fig.tight_layout()
#     fig.savefig(out_dir / "validation_comparison.png", dpi=130)
#     plt.close(fig)
#     written.append("validation_comparison.png")

#     # 3. Error distribution.
#     fig, ax = plt.subplots(figsize=(8, 4.5))
#     errors = 100 * (preds["soh_predicted"] - preds["soh"])
#     ax.hist(errors, bins=45, color="#4c72b0", alpha=0.85)
#     ax.axvline(0, color="k", linewidth=1)
#     ax.set_xlabel("Estimation error (SOH percentage points)")
#     ax.set_ylabel("Cycles")
#     ax.set_title(f"Out-of-sample error distribution\n"
#                  f"mean {errors.mean():+.2f}, "
#                  f"90% of cycles within {np.percentile(np.abs(errors), 90):.2f} points",
#                  fontsize=10)
#     ax.grid(alpha=0.3)
#     fig.tight_layout()
#     fig.savefig(out_dir / "error_distribution.png", dpi=130)
#     plt.close(fig)
#     written.append("error_distribution.png")

#     logger.info("Wrote %d plots to %s", len(written), out_dir)
#     return written


# def write_report(out_dir: Path, df: pd.DataFrame, ablation_results: Dict,
#                  plots: List[str]) -> Path:
#     """Assemble the Markdown evaluation report."""
#     soh_report_path = out_dir / "soh_training_report.json"
#     anomaly_report_path = out_dir / "anomaly_training_report.json"
#     soh_report = json.loads(soh_report_path.read_text()
#                             ) if soh_report_path.exists() else {}
#     anomaly_report = (
#         json.loads(anomaly_report_path.read_text()
#                    ) if anomaly_report_path.exists() else {}
#     )

#     lines: List[str] = []
#     add = lines.append

#     add("# Model Evaluation Report\n")
#     add("Generated by `python -m backend.batris.evaluate`.\n")
#     add(f"- Cycles: **{len(df)}**")
#     add(f"- Batteries: **{df['battery_id'].nunique()}** "
#         f"({', '.join(sorted(df['battery_id'].unique()))})")
#     add(f"- SOH range in data: **{100 * df['soh'].min():.1f}% - "
#         f"{100 * df['soh'].max():.1f}%**\n")

#     add("## 1. State of Health estimation\n")
#     add("Validation is **leave-one-battery-out**: the model is trained on all "
#         "cells but one and scored on the cell it never saw. This is the number "
#         "that reflects deployment, where every battery is new to the model.\n")
#     add("| Variant | Features | LOBO MAE (SOH pts) | LOBO R2 | Random-split MAE | Optimism factor |")
#     add("|---|---|---|---|---|---|")
#     for variant, entry in soh_report.get("variants", {}).items():
#         lobo = entry.get("lobo", {}).get("pooled", {})
#         base = entry.get("random_split_baseline", {})
#         factor = (lobo.get("mae", 0) /
#                   base["mae"]) if base.get("mae") else float("nan")
#         add(f"| `{variant}` | {entry.get('n_features')} | "
#             f"**{lobo.get('mae_soh_percentage_points', float('nan')):.2f}** | "
#             f"{lobo.get('r2', float('nan')):.3f} | "
#             f"{100 * base.get('mae', float('nan')):.2f} | {factor:.1f}x |")
#     add("")
#     add("The optimism factor is the ratio between the two validation methods. "
#         "A random cycle split places cycle *n* in training and cycle *n+1* in "
#         "test; those are near-identical, so the model can effectively copy the "
#         "answer. Published battery-SOH work frequently reports the optimistic "
#         "number.\n")

#     add("### Per-battery breakdown\n")
#     for variant, entry in soh_report.get("variants", {}).items():
#         per = entry.get("lobo", {}).get("per_battery", {})
#         if not per:
#             continue
#         add(f"**`{variant}`**\n")
#         add("| Held-out battery | Cycles | MAE (SOH pts) | RMSE | R2 |")
#         add("|---|---|---|---|---|")
#         for battery, stats in per.items():
#             add(f"| {battery} | {stats['n_cycles']} | "
#                 f"{stats['mae_soh_percentage_points']:.2f} | "
#                 f"{stats['rmse']:.4f} | {stats['r2']:+.3f} |")
#         add("")

#     add("### Uncertainty calibration\n")
#     for variant, entry in soh_report.get("variants", {}).items():
#         cal = entry.get("interval_calibration")
#         if not cal:
#             continue
#         add(f"- `{variant}`: the raw 90% quantile interval covered "
#             f"**{100 * cal['coverage_before']:.0f}%** of held-out points. "
#             f"Widening by **{cal['factor']:.2f}x** restores "
#             f"{100 * cal['coverage_after']:.0f}% coverage.")
#     add("")
#     add("Quantile regression is fitted in-distribution, so on an unseen cell the "
#         "raw interval is systematically too narrow. Reporting a 90% interval that "
#         "delivers 73% is worse than reporting no interval at all, because it "
#         "invites misplaced confidence in a safety-relevant number. The "
#         "calibration factor is derived from held-out residuals only.\n")

#     add("## 2. Feature ablation\n")
#     add("Each group is removed, then used alone, with LOBO re-run each time. "
#         "Feature importance alone is misleading when features are correlated; "
#         "removal shows what is genuinely irreplaceable.\n")
#     add("| Configuration | Features | MAE (SOH pts) | Change vs all features |")
#     add("|---|---|---|---|")
#     for name, stats in ablation_results.items():
#         label = name.replace("_", " ")
#         delta = stats["delta_vs_baseline"]
#         marker = "" if name == "all_features" else f"{delta:+.3f}"
#         add(f"| {label} | {stats['n_features']} | {stats['mae_soh_points']:.3f} | {marker} |")
#     add("")

#     add("## 3. Assessing a battery with no recorded history\n")
#     tier_report_path = out_dir / "tier_training_report.json"
#     if tier_report_path.exists():
#         tier_report = json.loads(tier_report_path.read_text()).get("tiers", {})
#         add("A separate model is trained and validated for each level of "
#             "information a user might have about a battery that is not in the "
#             "dataset. Validation is the same leave-one-battery-out protocol used "
#             "throughout.\n")
#         add("| Tier | Input | Signals | LOBO MAE (SOH pts) | R2 | Worst cell | Output |")
#         add("|---|---|---|---|---|---|---|")
#         for entry in sorted(tier_report.values(), key=lambda e: e["rank"]):
#             validation = entry["validation"]
#             add(f"| {entry['rank']} | {entry['display_name']} | "
#                 f"{entry['n_features']} | "
#                 f"**{validation['mae_soh_points']:.2f}** | "
#                 f"{validation['r2']:.3f} | "
#                 f"{validation['worst_battery_mae_soh_points']:.2f} | "
#                 f"{'Full report' if entry['reliable'] else 'Indicative only'} |")
#         add("")
#         add("Two results are worth drawing out.\n")
#         add("The first is that **tier 3 costs almost nothing**. Six numbers a "
#             "person can read off a charger display give up roughly 0.2 SOH points "
#             "against a fully instrumented charge curve. Most of the signal lives "
#             "in how a charge divides between its constant-current and "
#             "constant-voltage phases, and that ratio survives being reduced to a "
#             "few hand-typed figures. Useful battery assessment does not require "
#             "laboratory equipment.\n")
#         add("The second is that **tier 4 fails, and is reported as failing**. "
#             "With only the CC/CV split, R2 collapses and the worst cell misses by "
#             "13 SOH points. The platform still returns a number at this tier but "
#             "refuses to issue a reuse grade from it. Knowing where a method stops "
#             "working is part of reporting it honestly.\n")
#         add("A model per tier is used rather than one model with nulls passed for "
#             "missing inputs. XGBoost tolerates NaN, so the single-model approach "
#             "runs without complaint and returns a confident number drawn from a "
#             "feature distribution it was never fitted on, with nothing to signal "
#             "that anything is wrong. Per-tier training means the accuracy quoted "
#             "to a user is the accuracy measured for their situation.\n")
#     else:
#         add("Not generated. Run `python -m backend.batris.train_tiers` first.\n")

#     add("## 4. Anomaly detection\n")
#     validation = anomaly_report.get("validation", {})
#     if validation:
#         add(f"- False-alarm rate on unmodified data: "
#             f"**{100 * validation['false_alarm_rate']:.1f}%** "
#             f"({validation['n_clean_cycles']} cycles)")
#         add(f"- Mean recall across injected fault types: "
#             f"**{100 * validation['mean_recall']:.1f}%**\n")
#         add("| Injected fault | Recall | Rated critical | Mean score |")
#         add("|---|---|---|---|")
#         for fault, stats in validation.get("per_fault", {}).items():
#             add(f"| {fault.replace('_', ' ')} | {100 * stats['recall']:.1f}% | "
#                 f"{100 * stats['critical_rate']:.1f}% | {stats['mean_score']:.1f} |")
#         add("")
#         add("The dataset contains no labelled faults, so recall is measured by "
#             "stamping known physical fault signatures onto real healthy cycles "
#             "*inside an intact battery history*. Both numbers are reported "
#             "together because a detector that flags everything achieves perfect "
#             "recall and is useless.\n")

#     add("## 5. Figures\n")
#     for plot in plots:
#         add(f"![{plot}]({plot})\n")

#     add("## 6. Known limitations\n")
#     add("- **Four cells.** All from one chemistry (LCO 18650) at one ambient "
#         "temperature (24 C). Cell-to-cell variability cannot be characterised "
#         "from three training units, which is why honest confidence intervals "
#         "come out wide.")
#     add("- **No ambient temperature variation.** The thermal pathway is "
#         "implemented and exercised by measured cell temperature, but ambient "
#         "is constant in this dataset, so its effect is untested.")
#     add("- **No real faults.** Anomaly recall is measured against synthetic "
#         "injections, which is weaker evidence than field failure data.")
#     add("- **Single chemistry.** The multi-format round trip proves the code is "
#         "scale- and unit-correct, not that a model trained on LCO transfers to "
#         "LFP or NMC. That needs real multi-chemistry data. Requests for a "
#         "non-LCO format are flagged as extrapolation and their intervals widened "
#         "1.6x, but that factor is an engineering judgement rather than a "
#         "measured quantity.")
#     add("- **Tier 3 assumes a CC-CV charger.** The questionnaire asks for a "
#         "steady phase and a tapering phase. Multi-step or pulse charging does not "
#         "divide cleanly that way and those figures would be guesses.")
#     add("- **Estimates, not certifications.** Nothing here substitutes for an "
#         "accredited capacity test.\n")

#     path = out_dir / "EVALUATION.md"
#     path.write_text("\n".join(lines), encoding="utf-8")
#     return path


# def main(argv=None) -> int:
#     parser = argparse.ArgumentParser(
#         description="Generate the evaluation report.")
#     parser.add_argument("--data", type=Path, default=CYCLES_PATH)
#     parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
#     parser.add_argument("--plots", type=Path, default=PLOTS_DIR)
#     parser.add_argument("--skip-ablation", action="store_true")
#     parser.add_argument("--skip-plots", action="store_true")
#     args = parser.parse_args(argv)

#     if not args.data.exists():
#         logger.error(
#             "Missing %s. Run:  python -m backend.batris.build_dataset", args.data)
#         return 1

#     df = pd.read_csv(args.data, parse_dates=["timestamp"])
#     df = df[np.isfinite(df["soh"])].reset_index(drop=True)
#     args.reports.mkdir(parents=True, exist_ok=True)
#     args.plots.mkdir(parents=True, exist_ok=True)

#     ablation_results: Dict = {}
#     if not args.skip_ablation:
#         logger.info(
#             "Running feature ablation (leave-one-battery-out per config)...")
#         ablation_results = ablation(df)
#         with open(args.reports / "ablation.json", "w", encoding="utf-8") as fh:
#             json.dump(ablation_results, fh, indent=2)

#     plots: List[str] = []
#     if not args.skip_plots:
#         logger.info("Generating plots...")
#         plots = make_plots(df, args.plots)

#     path = write_report(args.reports, df, ablation_results, plots)
#     logger.info("Wrote evaluation report to %s", path)
#     return 0


# if __name__ == "__main__":
#     sys.exit(main())

"""
Stage 4: Generate the complete evaluation report.

    python -m backend.batris.evaluate

Creates a Markdown report and diagnostic plots by combining:
- SOH model validation results
- Anomaly detection results
- Feature importance analysis
"""

from __future__ import annotations

from .paths import CYCLES_PATH, PLOTS_DIR, REPORTS_DIR

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from .features import FEATURE_GROUPS, SOH_FEATURES
from .models.soh import DEFAULT_PARAMS, VARIANTS, SOHModel, features_for_variant

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluate")


def lobo_predictions(df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
    """Out-of-sample predictions for every cycle, via leave-one-battery-out."""
    import xgboost as xgb

    frames = []
    for held_out in sorted(df["battery_id"].unique()):
        train = df[df["battery_id"] != held_out]
        test = df[df["battery_id"] == held_out].copy()
        model = xgb.XGBRegressor(
            objective="reg:squarederror", **DEFAULT_PARAMS)
        model.fit(train[features], train["soh"])
        test["soh_predicted"] = model.predict(test[features])
        frames.append(test)
    return pd.concat(frames, ignore_index=True)


def ablation(df: pd.DataFrame) -> Dict[str, Dict]:
    """Measures how much each feature group affects the model.

    Feature importance can be misleading when features are related, so this checks
    performance after removing each group to see which features are actually useful.
    """
    results: Dict[str, Dict] = {}

    baseline = lobo_predictions(df, SOH_FEATURES)
    base_mae = mean_absolute_error(baseline["soh"], baseline["soh_predicted"])
    results["all_features"] = {
        "n_features": len(SOH_FEATURES),
        "mae": float(base_mae),
        "mae_soh_points": round(100 * base_mae, 3),
        "delta_vs_baseline": 0.0,
    }

    for group, members in FEATURE_GROUPS.items():
        remaining = [f for f in SOH_FEATURES if f not in members]
        if not remaining:
            continue
        preds = lobo_predictions(df, remaining)
        mae = mean_absolute_error(preds["soh"], preds["soh_predicted"])
        results[f"without_{group}"] = {
            "n_features": len(remaining),
            "mae": float(mae),
            "mae_soh_points": round(100 * mae, 3),
            "delta_vs_baseline": round(100 * (mae - base_mae), 3),
        }
        logger.info("  without %-22s MAE=%.4f (%+.3f SOH points vs all features)",
                    group, mae, 100 * (mae - base_mae))

    # Each group in isolation.
    for group, members in FEATURE_GROUPS.items():
        preds = lobo_predictions(df, members)
        mae = mean_absolute_error(preds["soh"], preds["soh_predicted"])
        results[f"only_{group}"] = {
            "n_features": len(members),
            "mae": float(mae),
            "mae_soh_points": round(100 * mae, 3),
            "delta_vs_baseline": round(100 * (mae - base_mae), 3),
        }
        logger.info("  only    %-22s MAE=%.4f", group, mae)

    return results


def make_plots(df: pd.DataFrame, out_dir: Path) -> List[str]:
    """Generate diagnostic figures. Returns the filenames written."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written: List[str] = []
    preds = lobo_predictions(df, SOH_FEATURES)

    # 1. SOH prediction accuracy: honest leave-one-battery-out validation.
    # This keeps only the model's real out-of-sample result and removes the
    # random-cycle comparison, which can be misleading because adjacent
    # cycles from the same battery may appear in both train and test sets.
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(
        100 * np.asarray(preds["soh"]),
        100 * np.asarray(preds["soh_predicted"]),
        s=12,
        alpha=0.45,
        edgecolors="none",
    )
    lo, hi = 55, 105
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Measured SOH (%)")
    ax.set_ylabel("Estimated SOH (%)")

    mae = mean_absolute_error(preds["soh"], preds["soh_predicted"])
    r2 = r2_score(preds["soh"], preds["soh_predicted"])
    ax.set_title(
        "SOH Estimation Accuracy\n"
        f"Leave-one-battery-out validation  •  MAE {100 * mae:.2f} pts, R² {r2:.3f}",
        fontsize=11,
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "soh_prediction_accuracy.png", dpi=130)
    plt.close(fig)
    written.append("soh_prediction_accuracy.png")

    # 2. SOH degradation trajectory for B0007 only.
    # B0007 is retained as the representative low-error battery requested
    # for the presentation-focused evaluation report.
    battery = "B0007"
    subset = preds[preds["battery_id"] == battery].sort_values("cycle_index")

    if subset.empty:
        logger.warning("Battery %s not found; skipping trajectory plot.", battery)
    else:
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.plot(
            subset["cycle_index"],
            100 * subset["soh"],
            label="Measured (reference discharge)",
            linewidth=1.8,
            color="#1f77b4",
        )
        ax.plot(
            subset["cycle_index"],
            100 * subset["soh_predicted"],
            label="Estimated (held-out model)",
            linewidth=1.4,
            color="#d62728",
            linestyle="--",
        )
        ax.axhline(80, color="grey", linestyle=":", linewidth=1)
        ax.text(2, 80.6, "80% end of first life", fontsize=7, color="grey")

        mae = mean_absolute_error(subset["soh"], subset["soh_predicted"])
        ax.set_title(
            f"{battery} — SOH Estimation Across Battery Lifecycle\n"
            f"Out-of-sample MAE {100 * mae:.2f} SOH points",
            fontsize=11,
        )
        ax.set_xlabel("Cycle")
        ax.set_ylabel("State of Health (%)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "soh_trajectory_B0007.png", dpi=130)
        plt.close(fig)
        written.append("soh_trajectory_B0007.png")

    # 3. Error distribution.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    errors = 100 * (preds["soh_predicted"] - preds["soh"])
    ax.hist(errors, bins=45, color="#4c72b0", alpha=0.85)
    ax.axvline(0, color="k", linewidth=1)
    ax.set_xlabel("Estimation error (SOH percentage points)")
    ax.set_ylabel("Cycles")
    ax.set_title(
        f"Out-of-sample error distribution\n"
        f"mean {errors.mean():+.2f}, "
        f"90% of cycles within {np.percentile(np.abs(errors), 90):.2f} points",
        fontsize=10,
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "error_distribution.png", dpi=130)
    plt.close(fig)
    written.append("error_distribution.png")

    logger.info("Wrote %d plots to %s", len(written), out_dir)
    return written

def write_report(out_dir: Path, df: pd.DataFrame, ablation_results: Dict,
                 plots: List[str]) -> Path:
    """Assemble the Markdown evaluation report."""
    soh_report_path = out_dir / "soh_training_report.json"
    anomaly_report_path = out_dir / "anomaly_training_report.json"
    soh_report = json.loads(soh_report_path.read_text()
                            ) if soh_report_path.exists() else {}
    anomaly_report = (
        json.loads(anomaly_report_path.read_text()
                   ) if anomaly_report_path.exists() else {}
    )

    lines: List[str] = []
    add = lines.append

    add("# Model Evaluation Report\n")
    add("Generated by `python -m backend.batris.evaluate`.\n")
    add(f"- Cycles: **{len(df)}**")
    add(f"- Batteries: **{df['battery_id'].nunique()}** "
        f"({', '.join(sorted(df['battery_id'].unique()))})")
    add(f"- SOH range in data: **{100 * df['soh'].min():.1f}% - "
        f"{100 * df['soh'].max():.1f}%**\n")

    add("## 1. State of Health estimation\n")
    add(
        "SOH is evaluated using **leave-one-battery-out validation**: the model "
        "is trained on all batteries except one and then tested on the completely "
        "unseen battery. This gives an out-of-sample estimate of how the model "
        "performs when a new battery is presented to BATRIS.\n"
    )

    add("| Variant | Features | LOBO MAE (SOH pts) | LOBO R2 |")
    add("|---|---|---|---|")
    for variant, entry in soh_report.get("variants", {}).items():
        lobo = entry.get("lobo", {}).get("pooled", {})
        add(
            f"| `{variant}` | {entry.get('n_features')} | "
            f"**{lobo.get('mae_soh_percentage_points', float('nan')):.2f}** | "
            f"{lobo.get('r2', float('nan')):.3f} |"
        )
    add("")

    add("### Representative battery trajectory\n")
    add(
        "The generated lifecycle plot focuses on **B0007**, where the held-out "
        "model tracks the measured SOH trajectory across cycles. "
        "The plotted estimate is produced without training on B0007.\n"
    )
    add("![B0007 SOH trajectory](../plots/soh_trajectory_B0007.png)\n")

    add("### SOH prediction accuracy\n")
    add(
        "The parity plot compares measured SOH with BATRIS's out-of-sample "
        "estimated SOH. Points closer to the diagonal indicate closer agreement "
        "between the estimate and the reference measurement.\n"
    )
    add("![SOH prediction accuracy](../plots/soh_prediction_accuracy.png)\n")

    add("### Per-battery breakdown\n")
    for variant, entry in soh_report.get("variants", {}).items():
        per = entry.get("lobo", {}).get("per_battery", {})
        if not per:
            continue
        add(f"**`{variant}`**\n")
        add("| Held-out battery | Cycles | MAE (SOH pts) | RMSE | R2 |")
        add("|---|---|---|---|---|")
        for battery, stats in per.items():
            add(
                f"| {battery} | {stats['n_cycles']} | "
                f"{stats['mae_soh_percentage_points']:.2f} | "
                f"{stats['rmse']:.4f} | {stats['r2']:+.3f} |"
            )
        add("")

    add("### Uncertainty calibration\n")
    for variant, entry in soh_report.get("variants", {}).items():
        cal = entry.get("interval_calibration")
        if not cal:
            continue
        add(
            f"- `{variant}`: the raw 90% quantile interval covered "
            f"**{100 * cal['coverage_before']:.0f}%** of held-out points. "
            f"Widening by **{cal['factor']:.2f}x** restores "
            f"{100 * cal['coverage_after']:.0f}% coverage."
        )
    add("")

    add(
        "Quantile regression is fitted in-distribution, so on an unseen cell the "
        "raw interval is systematically too narrow. Reporting a 90% interval that "
        "does not achieve its intended coverage can create misplaced confidence "
        "in a safety-relevant number. The calibration factor is derived from "
        "held-out residuals only.\n"
    )

    add("## 2. Feature ablation\n")
    add("Each group is removed, then used alone, with LOBO re-run each time. "
        "Feature importance alone is misleading when features are correlated; "
        "removal shows what is genuinely irreplaceable.\n")
    add("| Configuration | Features | MAE (SOH pts) | Change vs all features |")
    add("|---|---|---|---|")
    for name, stats in ablation_results.items():
        label = name.replace("_", " ")
        delta = stats["delta_vs_baseline"]
        marker = "" if name == "all_features" else f"{delta:+.3f}"
        add(f"| {label} | {stats['n_features']} | {stats['mae_soh_points']:.3f} | {marker} |")
    add("")

    add("## 3. Assessing a battery with no recorded history\n")
    tier_report_path = out_dir / "tier_training_report.json"
    if tier_report_path.exists():
        tier_report = json.loads(tier_report_path.read_text()).get("tiers", {})
        add("A separate model is trained and validated for each level of "
            "information a user might have about a battery that is not in the "
            "dataset. Validation is the same leave-one-battery-out protocol used "
            "throughout.\n")
        add("| Tier | Input | Signals | LOBO MAE (SOH pts) | R2 | Worst cell | Output |")
        add("|---|---|---|---|---|---|---|")
        for entry in sorted(tier_report.values(), key=lambda e: e["rank"]):
            validation = entry["validation"]
            add(f"| {entry['rank']} | {entry['display_name']} | "
                f"{entry['n_features']} | "
                f"**{validation['mae_soh_points']:.2f}** | "
                f"{validation['r2']:.3f} | "
                f"{validation['worst_battery_mae_soh_points']:.2f} | "
                f"{'Full report' if entry['reliable'] else 'Indicative only'} |")
        add("")
        add("Two results are worth drawing out.\n")
        add("The first is that **tier 3 costs almost nothing**. Six numbers a "
            "person can read off a charger display give up roughly 0.2 SOH points "
            "against a fully instrumented charge curve. Most of the signal lives "
            "in how a charge divides between its constant-current and "
            "constant-voltage phases, and that ratio survives being reduced to a "
            "few hand-typed figures. Useful battery assessment does not require "
            "laboratory equipment.\n")
        add("The second is that **tier 4 fails, and is reported as failing**. "
            "With only the CC/CV split, R2 collapses and the worst cell misses by "
            "13 SOH points. The platform still returns a number at this tier but "
            "refuses to issue a reuse grade from it. Knowing where a method stops "
            "working is part of reporting it honestly.\n")
        add("A model per tier is used rather than one model with nulls passed for "
            "missing inputs. XGBoost tolerates NaN, so the single-model approach "
            "runs without complaint and returns a confident number drawn from a "
            "feature distribution it was never fitted on, with nothing to signal "
            "that anything is wrong. Per-tier training means the accuracy quoted "
            "to a user is the accuracy measured for their situation.\n")
    else:
        add("Not generated. Run `python -m backend.batris.train_tiers` first.\n")

    add("## 4. Anomaly detection\n")
    validation = anomaly_report.get("validation", {})
    if validation:
        add(f"- False-alarm rate on unmodified data: "
            f"**{100 * validation['false_alarm_rate']:.1f}%** "
            f"({validation['n_clean_cycles']} cycles)")
        add(f"- Mean recall across injected fault types: "
            f"**{100 * validation['mean_recall']:.1f}%**\n")
        add("| Injected fault | Recall | Rated critical | Mean score |")
        add("|---|---|---|---|")
        for fault, stats in validation.get("per_fault", {}).items():
            add(f"| {fault.replace('_', ' ')} | {100 * stats['recall']:.1f}% | "
                f"{100 * stats['critical_rate']:.1f}% | {stats['mean_score']:.1f} |")
        add("")
        add("The dataset contains no labelled faults, so recall is measured by "
            "stamping known physical fault signatures onto real healthy cycles "
            "*inside an intact battery history*. Both numbers are reported "
            "together because a detector that flags everything achieves perfect "
            "recall and is useless.\n")

    add("## 5. Figures\n")
    for plot in plots:
        add(f"![{plot}](../plots/{plot})\n")

    add("## 6. Known limitations\n")
    add("- **Four cells.** All from one chemistry (LCO 18650) at one ambient "
        "temperature (24 C). Cell-to-cell variability cannot be characterised "
        "from three training units, which is why honest confidence intervals "
        "come out wide.")
    add("- **No ambient temperature variation.** The thermal pathway is "
        "implemented and exercised by measured cell temperature, but ambient "
        "is constant in this dataset, so its effect is untested.")
    add("- **No real faults.** Anomaly recall is measured against synthetic "
        "injections, which is weaker evidence than field failure data.")
    add("- **Single chemistry.** The multi-format round trip proves the code is "
        "scale- and unit-correct, not that a model trained on LCO transfers to "
        "LFP or NMC. That needs real multi-chemistry data. Requests for a "
        "non-LCO format are flagged as extrapolation and their intervals widened "
        "1.6x, but that factor is an engineering judgement rather than a "
        "measured quantity.")
    add("- **Tier 3 assumes a CC-CV charger.** The questionnaire asks for a "
        "steady phase and a tapering phase. Multi-step or pulse charging does not "
        "divide cleanly that way and those figures would be guesses.")
    add("- **Estimates, not certifications.** Nothing here substitutes for an "
        "accredited capacity test.\n")

    path = out_dir / "EVALUATION.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the evaluation report.")
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--reports", type=Path, default=REPORTS_DIR)
    parser.add_argument("--plots", type=Path, default=PLOTS_DIR)
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--skip-plots", action="store_true")
    args = parser.parse_args(argv)

    if not args.data.exists():
        logger.error(
            "Missing %s. Run:  python -m backend.batris.build_dataset", args.data)
        return 1

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df[np.isfinite(df["soh"])].reset_index(drop=True)
    args.reports.mkdir(parents=True, exist_ok=True)
    args.plots.mkdir(parents=True, exist_ok=True)

    ablation_results: Dict = {}
    if not args.skip_ablation:
        logger.info(
            "Running feature ablation (leave-one-battery-out per config)...")
        ablation_results = ablation(df)
        with open(args.reports / "ablation.json", "w", encoding="utf-8") as fh:
            json.dump(ablation_results, fh, indent=2)

    plots: List[str] = []
    if not args.skip_plots:
        logger.info("Generating plots...")
        plots = make_plots(df, args.plots)

    path = write_report(args.reports, df, ablation_results, plots)
    logger.info("Wrote evaluation report to %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())