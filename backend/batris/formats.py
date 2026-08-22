"""
Battery format registry used by ingestion, features and safety logic.
"""

from __future__ import annotations

import functools
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict

from .paths import CUSTOM_FORMATS_PATH


BUILTIN_FORMATS = {
    "NASA_18650_LCO_2AH": {
        "display_name": "18650 Cylindrical LCO 2.0 Ah",
        "chemistry": "LCO",
        "form_factor": "cylindrical_18650",
        "rated_capacity_ah": 2.0,
        "nominal_voltage_v": 3.7,
        "v_max": 4.2,
        "v_min": 2.5,
        "v_min_absolute": 2.0,
        "cells_in_series": 1,
        "cells_in_parallel": 1,
        "max_charge_c_rate": 0.75,
        "max_discharge_c_rate": 2.0,
        "temp_warn_c": 45.0,
        "temp_critical_c": 60.0,
        "temp_max_charge_c": 45.0,
        "temp_min_charge_c": 0.0,
        "eol_soh": 0.80,
        "second_life_floor_soh": 0.60,
    },
    "LFP_PRISMATIC_280AH": {
        "display_name": "Prismatic LFP 280 Ah",
        "chemistry": "LFP",
        "form_factor": "prismatic",
        "rated_capacity_ah": 280.0,
        "nominal_voltage_v": 3.2,
        "v_max": 3.65,
        "v_min": 2.50,
        "v_min_absolute": 2.00,
        "cells_in_series": 1,
        "cells_in_parallel": 1,
        "max_charge_c_rate": 0.5,
        "max_discharge_c_rate": 1.0,
        "temp_warn_c": 50.0,
        "temp_critical_c": 65.0,
        "temp_max_charge_c": 45.0,
        "temp_min_charge_c": 0.0,
        "eol_soh": 0.80,
        "second_life_floor_soh": 0.60,
    },
    "NMC_POUCH_50AH": {
        "display_name": "Pouch NMC811 50 Ah",
        "chemistry": "NMC",
        "form_factor": "pouch",
        "rated_capacity_ah": 50.0,
        "nominal_voltage_v": 3.7,
        "v_max": 4.2,
        "v_min": 3.0,
        "v_min_absolute": 2.5,
        "cells_in_series": 1,
        "cells_in_parallel": 1,
        "max_charge_c_rate": 1.5,
        "max_discharge_c_rate": 3.0,
        "temp_warn_c": 45.0,
        "temp_critical_c": 60.0,
        "temp_max_charge_c": 45.0,
        "temp_min_charge_c": 5.0,
        "eol_soh": 0.80,
        "second_life_floor_soh": 0.60,
    },
    "E2W_PACK_13S4P_NMC": {
        "display_name": "E-2W Pack 13S4P NMC (48 V, 10 Ah)",
        "chemistry": "NMC",
        "form_factor": "cylindrical_21700_pack",
        "rated_capacity_ah": 10.0,
        "nominal_voltage_v": 48.1,
        "v_max": 54.6,
        "v_min": 39.0,
        "v_min_absolute": 32.5,
        "cells_in_series": 13,
        "cells_in_parallel": 4,
        "max_charge_c_rate": 1.0,
        "max_discharge_c_rate": 3.0,
        "temp_warn_c": 45.0,
        "temp_critical_c": 60.0,
        "temp_max_charge_c": 45.0,
        "temp_min_charge_c": 5.0,
        "eol_soh": 0.80,
        "second_life_floor_soh": 0.60,
    },
}

CUSTOM_FORMAT_DEFAULTS = {
    "cells_in_series": 1,
    "cells_in_parallel": 1,
    "max_charge_c_rate": 0.5,
    "max_discharge_c_rate": 1.0,
    "temp_warn_c": 40.0,
    "temp_critical_c": 55.0,
    "temp_max_charge_c": 45.0,
    "temp_min_charge_c": 0.0,
    "eol_soh": 0.80,
    "second_life_floor_soh": 0.60,
}


@dataclass(frozen=True)
class BatteryFormat:
    key: str
    display_name: str
    chemistry: str
    form_factor: str
    rated_capacity_ah: float
    nominal_voltage_v: float
    v_max: float
    v_min: float
    v_min_absolute: float
    cells_in_series: int
    cells_in_parallel: int
    max_charge_c_rate: float
    max_discharge_c_rate: float
    temp_warn_c: float
    temp_critical_c: float
    temp_max_charge_c: float
    temp_min_charge_c: float
    eol_soh: float
    second_life_floor_soh: float

    def to_c_rate(self, current_a):
        return current_a / self.rated_capacity_ah

    def to_soc_fraction(self, charge_ah):
        return charge_ah / self.rated_capacity_ah

    def to_v_norm(self, voltage_v):
        return (voltage_v - self.v_min) / (self.v_max - self.v_min)

    def from_v_norm(self, v_norm):
        return v_norm * (self.v_max - self.v_min) + self.v_min

    @property
    def rated_energy_wh(self) -> float:
        return self.rated_capacity_ah * self.nominal_voltage_v

    def as_dict(self) -> Dict:
        return asdict(self)


@functools.lru_cache(maxsize=1)
def _load_registry(custom_mtime: float = 0.0) -> Dict[str, BatteryFormat]:
    registry = {
        key: BatteryFormat(key=key, **spec)
        for key, spec in BUILTIN_FORMATS.items()
    }

    if CUSTOM_FORMATS_PATH.exists():
        try:
            raw = json.loads(CUSTOM_FORMATS_PATH.read_text(encoding="utf-8"))
            for key, spec in (raw.get("formats") or {}).items():
                try:
                    registry[key] = BatteryFormat(key=key, **spec)
                except TypeError as exc:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Skipping malformed custom format %r: %s", key, exc
                    )
        except (OSError, json.JSONDecodeError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Could not load custom formats from %s: %s", CUSTOM_FORMATS_PATH, exc
            )

    return registry


def _custom_mtime() -> float:
    return CUSTOM_FORMATS_PATH.stat().st_mtime if CUSTOM_FORMATS_PATH.exists() else 0.0


def register_custom_format(spec: Dict) -> BatteryFormat:
    required = (
        "display_name", "chemistry", "form_factor",
        "rated_capacity_ah", "nominal_voltage_v", "v_max", "v_min",
    )
    missing = [field for field in required if spec.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Custom format is missing required fields: {missing}")

    key = str(spec.get("key") or spec["display_name"]).strip().upper()
    key = "".join(c if c.isalnum() else "_" for c in key).strip("_")
    if not key:
        raise ValueError("Could not derive a valid format key from the name given.")

    entry = {**CUSTOM_FORMAT_DEFAULTS}
    for field_name in (*required, *CUSTOM_FORMAT_DEFAULTS):
        if spec.get(field_name) not in (None, ""):
            entry[field_name] = spec[field_name]

    entry["rated_capacity_ah"] = float(entry["rated_capacity_ah"])
    entry["nominal_voltage_v"] = float(entry["nominal_voltage_v"])
    entry["v_max"] = float(entry["v_max"])
    entry["v_min"] = float(entry["v_min"])

    if entry["v_max"] <= entry["v_min"]:
        raise ValueError("Maximum voltage must exceed minimum voltage.")
    if not (entry["v_min"] <= entry["nominal_voltage_v"] <= entry["v_max"]):
        raise ValueError(
            "Nominal voltage must lie between the minimum and maximum voltages."
        )
    if entry["rated_capacity_ah"] <= 0:
        raise ValueError("Rated capacity must be greater than zero.")

    entry["v_min_absolute"] = round(0.8 * entry["v_min"], 3)
    if spec.get("v_min_absolute") not in (None, ""):
        entry["v_min_absolute"] = float(spec["v_min_absolute"])

    CUSTOM_FORMATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CUSTOM_FORMATS_PATH.exists():
        existing = json.loads(CUSTOM_FORMATS_PATH.read_text(encoding="utf-8")) or {}
    formats = existing.get("formats") or {}
    formats[key] = entry
    CUSTOM_FORMATS_PATH.write_text(
        json.dumps({"formats": formats}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    _load_registry.cache_clear()
    return get_format(key)


def get_format(key: str, registry_path: Path | str | None = None) -> BatteryFormat:
    # registry_path is kept for API compatibility.
    if registry_path is not None:
        path = Path(registry_path)
        if path.exists() and path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            registry = {
                item_key: BatteryFormat(key=item_key, **spec)
                for item_key, spec in (raw.get("formats") or {}).items()
            }
        else:
            registry = _load_registry(_custom_mtime())
    else:
        registry = _load_registry(_custom_mtime())

    if key not in registry:
        raise KeyError(
            f"Unknown battery format {key!r}. Known formats: {sorted(registry)}."
        )
    return registry[key]


def list_formats(registry_path: Path | str | None = None) -> Dict[str, BatteryFormat]:
    return dict(_load_registry(_custom_mtime()))
