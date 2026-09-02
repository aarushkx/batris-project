from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "nasa"
GENERATED_DIR = PROJECT_ROOT / "generated"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = GENERATED_DIR / "reports"
PLOTS_DIR = GENERATED_DIR / "plots"
KEYS_DIR = GENERATED_DIR / "keys"
PASSPORTS_DIR = GENERATED_DIR / "passports"
CUSTOM_FORMATS_PATH = GENERATED_DIR / "custom_formats.json"
MODELS_DIR = PROJECT_ROOT / "models"
CYCLES_PATH = PROCESSED_DIR / "cycles.csv"
TIMELINES_DIR = GENERATED_DIR / "timelines"
