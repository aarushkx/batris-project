"""
Demonstrates that the pipeline works with different battery formats.

    python -m backend.batris.demo_multiformat

The script converts NASA battery data into a different battery format and checks
whether the same processing pipeline can handle it.

It verifies that the feature extraction and normalization are independent of
battery size and units.

This does not prove that a model trained on one chemistry will accurately predict
another chemistry. Real multi-chemistry data would be required for that.
"""

from __future__ import annotations

from .paths import MODELS_DIR

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .features import SOH_FEATURES, build_feature_table
from .formats import get_format
from .ingest.generic_csv import load_csv
from .ingest.nasa_mat import load_battery

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo_multiformat")


def rescale_to_format(
    records, source_key: str, target_key: str,
) -> pd.DataFrame:
    """Convert CycleRecords into generic-CSV rows expressed in another format."""
    source = get_format(source_key)
    target = get_format(target_key)
    capacity_ratio = target.rated_capacity_ah / source.rated_capacity_ah
    # Adjusts resistance values after scaling voltage and current.
    # Since resistance depends on voltage and current, it must be scaled to keep
    # the converted battery data physically consistent.
    window_ratio = (target.v_max - target.v_min) / \
        (source.v_max - source.v_min)
    resistance_ratio = window_ratio / capacity_ratio

    rows = []
    for record in records:
        for phase_name, phase in (("charge", record.charge),
                                  ("discharge", record.discharge)):
            if phase is None:
                continue
          # Maps voltage values to the target battery's voltage range while keeping the
          # same relative state of charge.
            v_norm = source.to_v_norm(phase.voltage_v)
            voltage = target.from_v_norm(v_norm)

            for i in range(len(phase.time_s)):
                rows.append({
                    "battery_id": f"{record.battery_id}-NMC",
                    "cycle_index": record.cycle_index,
                    "phase": phase_name,
                    "timestamp": record.timestamp.isoformat(),
                    "time_s": float(phase.time_s[i]),
                    "voltage_v": float(voltage[i]),
                    "current_a": float(phase.current_a[i] * capacity_ratio),
                    "temperature_c": float(phase.temperature_c[i]),
                    "ambient_temp_c": record.ambient_temp_c,
                    "capacity_ah": (
                        float(record.measured_capacity_ah * capacity_ratio)
                        if record.measured_capacity_ah else np.nan
                    ),
                    "re_ohm": (
                        float(record.impedance.re_ohm * resistance_ratio)
                        if record.impedance else np.nan
                    ),
                    "rct_ohm": (
                        float(record.impedance.rct_ohm * resistance_ratio)
                        if record.impedance else np.nan
                    ),
                })
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Multi-format round-trip demo.")
    parser.add_argument("--battery", default="B0005")
    parser.add_argument("--source-format", default="NASA_18650_LCO_2AH")
    parser.add_argument("--target-format", default="NMC_POUCH_50AH")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/nasa"))
    parser.add_argument("--out-dir", type=Path,
                        default=Path("data/raw/generic_csv"))
    args = parser.parse_args(argv)

    source = get_format(args.source_format)
    target = get_format(args.target_format)

    logger.info("=" * 72)
    logger.info("MULTI-FORMAT ROUND-TRIP TEST")
    logger.info("  source: %-28s %.1f Ah, %s, %.2f-%.2f V",
                args.source_format, source.rated_capacity_ah, source.chemistry,
                source.v_min, source.v_max)
    logger.info("  target: %-28s %.1f Ah, %s, %.2f-%.2f V",
                args.target_format, target.rated_capacity_ah, target.chemistry,
                target.v_min, target.v_max)
    logger.info("=" * 72)

    # 1. Original path: NASA .mat -> features
    mat_path = args.raw_dir / f"{args.battery}.mat"
    if not mat_path.exists():
        logger.error("Missing %s", mat_path)
        return 1
    original_records = load_battery(mat_path, format_key=args.source_format)
    original_features = build_feature_table(original_records)

    # 2. Rescale into the target format and write generic CSV
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / f"{args.battery}_as_{args.target_format}.csv"
    rescale_to_format(original_records, args.source_format, args.target_format) \
        .to_csv(csv_path, index=False)
    logger.info("Wrote rescaled telemetry to %s", csv_path)

    # 3. Re-ingest through the generic CSV adapter under the new format
    rescaled_records = load_csv(csv_path, format_key=args.target_format)
    rescaled_features = build_feature_table(rescaled_records)

    # 4. Compare the dimensionless features
    logger.info("-" * 72)
    logger.info(
        "Feature agreement after format change (should be near-identical):")

    n = min(len(original_features), len(rescaled_features))
    worst_feature, worst_error = None, 0.0
    for feature in SOH_FEATURES:
        a = original_features[feature].to_numpy(dtype=float)[:n]
        b = rescaled_features[feature].to_numpy(dtype=float)[:n]
        both = np.isfinite(a) & np.isfinite(b)
        if both.sum() < 5:
            continue
        scale = max(float(np.nanstd(a[both])), 1e-6)
        error = float(np.nanmax(np.abs(a[both] - b[both])) / scale)
        if error > worst_error:
            worst_feature, worst_error = feature, error

    logger.info("  compared %d cycles across %d features",
                n, len(SOH_FEATURES))
    logger.info("  largest deviation: %s at %.4f standard deviations",
                worst_feature, worst_error)

    soh_a = original_features["soh"].to_numpy(dtype=float)[:n]
    soh_b = rescaled_features["soh"].to_numpy(dtype=float)[:n]
    soh_error = float(np.nanmax(np.abs(soh_a - soh_b)))
    logger.info("  largest SOH difference: %.6f (%.4f percentage points)",
                soh_error, 100 * soh_error)

    # 5. Same trained model, both formats
    try:
        from .models.soh import SOHModel
        model = SOHModel.load(MODELS_DIR, variant="provenance_free")
        pred_a = model.predict(original_features)
        pred_b = model.predict(rescaled_features)
        delta = float(np.nanmax(np.abs(pred_a[:n] - pred_b[:n])))
        logger.info("-" * 72)
        logger.info("Same trained model applied to both formats:")
        logger.info("  max estimate difference: %.4f SOH (%.3f percentage points)",
                    delta, 100 * delta)
        passed = delta < 0.01
    except FileNotFoundError:
        logger.warning("No trained model found; skipping model comparison.")
        passed = worst_error < 0.01

    logger.info("=" * 72)
    if passed and worst_error < 0.05:
        logger.info("PASS: the pipeline produced equivalent results for a battery "
                    "25x larger with a different voltage window.")
    else:
        logger.warning("FAIL: results diverged across formats; the normalisation "
                       "layer is not scale-invariant.")
        return 1
    logger.info("Note: this proves unit and scale correctness. It does NOT prove "
                "the model transfers across real chemistries -- see README.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
