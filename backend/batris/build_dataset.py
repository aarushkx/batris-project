"""
Stage 1 of the project.

This file takes raw battery data and converts it into a feature table
that can later be used by the machine learning model.

Example:

    python -m backend.batris.build_dataset --source nasa --input data/raw/nasa \
                                --output data/processed/cycles.csv
"""

from __future__ import annotations

from .paths import CYCLES_PATH

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from .features import SOH_FEATURES, build_feature_table
from .formats import list_formats


# Set up logging so we can see what the script is doing.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("build_dataset")


def load_records(
    source: str,
    input_path: Path,
    format_key: str
):
    """Load battery data using the correct input adapter."""

    # If the data is from NASA, use the NASA adapter.
    if source == "nasa":
        from .ingest.nasa_mat import load_directory
        return load_directory(
            input_path,
            format_key=format_key
        )

    # If the data is CSV, use the generic CSV adapter.
    if source == "csv":
        from .ingest.generic_csv import load_csv_directory
        return load_csv_directory(
            input_path,
            format_key=format_key
        )

    # Stop if an unsupported data source was given.
    raise ValueError(
        f"Unknown source {source!r}. Supported: nasa, csv"
    )


def main(argv=None) -> int:

    # Create the command-line argument parser.
    parser = argparse.ArgumentParser(
        description="Build the cycle feature table from raw battery telemetry."
    )

    # Choose where the raw data comes from.
    parser.add_argument(
        "--source",
        default="nasa",
        choices=["nasa", "csv"],
        help="Ingest adapter to use (default: nasa)"
    )

    # Path to the raw data folder.
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/nasa"),
        help="Directory containing the raw data files"
    )

    # Path where the final feature table should be saved.
    parser.add_argument(
        "--output",
        type=Path,
        default=CYCLES_PATH,
        help="Where to write the feature table"
    )

    # Select the type of battery being used.
    parser.add_argument(
        "--format",
        dest="format_key",
        default="NASA_18650_LCO_2AH",
        help="Battery format key from built-in battery format registry"
    )

    # Option to display all available battery formats.
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="Print the registered battery formats and exit"
    )

    args = parser.parse_args(argv)

    # If the user only wants to see the available battery formats,
    # print them and stop the program.
    if args.list_formats:
        for key, fmt in list_formats().items():
            print(
                f"  {key:<28} {fmt.display_name}  "
                f"({fmt.chemistry}, {fmt.rated_capacity_ah} Ah)"
            )

        return 0

    # Show what type of data we are loading.
    logger.info(
        "Ingesting %s data from %s (format=%s)",
        args.source,
        args.input,
        args.format_key
    )

    # Read the raw data and convert it into CycleRecords.
    records = load_records(
        args.source,
        args.input,
        args.format_key
    )

    logger.info(
        "Loaded %d cycle records",
        len(records)
    )

    # Convert the cycle records into the final feature table.
    df = build_feature_table(records)

    # ------------------------------------------------------------
    # Check the quality of the generated dataset.
    # ------------------------------------------------------------

    logger.info("-" * 68)

    logger.info(
        "Feature table: %d rows x %d columns",
        len(df),
        df.shape[1]
    )

    # Print some basic information for every battery.
    for battery_id, group in df.groupby("battery_id"):
        logger.info(
            "  %-7s cycles=%3d  SOH %.3f -> %.3f  span=%.0f days",
            battery_id,
            len(group),
            group["soh"].iloc[0],
            group["soh"].iloc[-1],
            group["calendar_age_days"].iloc[-1],
        )

    # Find out how many values are missing in each model feature.
    missing = (
        df[SOH_FEATURES]
        .isna()
        .mean()
        .sort_values(ascending=False)
    )

    incomplete = missing[missing > 0]

    if len(incomplete):

        logger.info(
            "  Features with missing values (XGBoost handles NaN natively):"
        )

        for name, frac in incomplete.items():
            logger.info(
                "    %-26s %5.1f%% missing",
                name,
                100 * frac
            )

    else:
        logger.info(
            "  No missing values in any model feature."
        )

    logger.info("-" * 68)

    # Create the output folder if it does not already exist.
    args.output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Save the feature table as a CSV file.
    df.to_csv(
        args.output,
        index=False
    )

    logger.info(
        "Wrote %s",
        args.output
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
