from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "nasa"
PROCESSED_DIR = DATA_DIR / "processed"
GENERATED_DIR = PROJECT_ROOT / "generated"
CUSTOM_FORMATS_PATH = GENERATED_DIR / "custom_formats.json"
CYCLES_PATH = PROCESSED_DIR / "cycles.csv"