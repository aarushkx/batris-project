"""
Defines input tiers for batteries without previous history.

Different users have different amounts of available data, so the platform uses
separate models for each input level instead of filling missing values.

Each tier is trained and tested using only the data it expects, giving a more
reliable estimate. Lower-data tiers may provide less accurate results and are
marked accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class InputField:
    """One question put to the user."""

    key: str
    label: str
    unit: str
    kind: str = "number"          # number | text | select
    required: bool = True
    help: str = ""
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    placeholder: str = ""

    def as_dict(self) -> Dict:
        return {
            "key": self.key, "label": self.label, "unit": self.unit,
            "kind": self.kind, "required": self.required, "help": self.help,
            "min": self.minimum, "max": self.maximum,
            "placeholder": self.placeholder,
        }


@dataclass(frozen=True)
class InputTier:
    """A named level of available information."""

    key: str
    rank: int                     # 1 = richest
    display_name: str
    description: str
    features: List[str]
    source: str                   # telemetry | manual | measurement
    fields: List[InputField] = field(default_factory=list)
    reliable: bool = True         # False => indicative only, no reuse grade

    def as_dict(self) -> Dict:
        return {
            "key": self.key, "rank": self.rank, "display_name": self.display_name,
            "description": self.description, "source": self.source,
            "n_features": len(self.features), "reliable": self.reliable,
            "fields": [f.as_dict() for f in self.fields],
        }


# ---------------------------------------------------------------------------
# Shared questionnaire fields
# ---------------------------------------------------------------------------

FIELD_FORMAT = InputField(
    "format_key", "Battery format", "", kind="select",
    help="Select the closest match, or register a custom format below.",
)
FIELD_AMBIENT = InputField(
    "ambient_temp_c", "Ambient temperature during charge", "degC",
    required=False, minimum=-30, maximum=60, placeholder="25",
    help="Room or outdoor temperature while the battery was charging.",
)
FIELD_PEAK_TEMP = InputField(
    "peak_temp_c", "Peak battery temperature during charge", "degC",
    required=False, minimum=-30, maximum=100, placeholder="32",
    help="Highest temperature the pack reached. Most BMS apps show this. "
         "Leave blank if unknown.",
)

# Tier 3 questionnaire fields.
# These values can be collected from a charger display, BMS app or simple timing.
# The goal is to estimate battery health without requiring lab equipment.
TIER3_FIELDS = [
    FIELD_FORMAT,
    InputField(
        "charge_current_a", "Charging current (steady phase)", "A",
        minimum=0.01, maximum=1000, placeholder="1.5",
        help="The current your charger holds while the battery is filling, "
             "before it starts tapering off. Shown on most smart chargers.",
    ),
    InputField(
        "cc_duration_min", "Time at steady current", "minutes",
        minimum=1, maximum=6000, placeholder="55",
        help="How long the current stayed steady, from the start of charging "
             "until it began dropping.",
    ),
    InputField(
        "cv_duration_min", "Time tapering to full", "minutes",
        minimum=0, maximum=6000, placeholder="40",
        help="How long the charger spent with the current falling, from when it "
             "began dropping until charging stopped.",
    ),
    InputField(
        "total_charge_ah", "Total charge delivered", "Ah",
        required=False, minimum=0.01, maximum=10000, placeholder="1.6",
        help="Amp-hours put in during this charge. If your charger reports watt-"
             "hours instead, use the kWh field below. Leave blank to estimate it.",
    ),
    InputField(
        "total_charge_kwh", "or total energy delivered", "kWh",
        required=False, minimum=0.0001, maximum=1000, placeholder="",
        help="Alternative to amp-hours. Converted using the pack's nominal voltage.",
    ),
    FIELD_PEAK_TEMP,
    FIELD_AMBIENT,
]

# Optional user-provided context.
# These values are not used by the model. They only help with safety checks
# and passport information.
CONTEXT_FIELDS = [
    InputField(
        "battery_id", "Battery identifier or serial", "", kind="text",
        required=False, placeholder="PACK-001",
        help="Used to label the passport. Any string.",
    ),
    InputField(
        "cycle_count", "Approximate cycle count", "cycles",
        required=False, minimum=0, maximum=20000, placeholder="",
        help="Rough count if known. Does not affect the estimate -- the model "
             "reads the battery's present condition, not its paperwork.",
    ),
    InputField(
        "age_months", "Age since manufacture", "months",
        required=False, minimum=0, maximum=600, placeholder="",
        help="Used for context in the passport only.",
    ),
    InputField(
        "min_voltage_seen_v", "Lowest voltage observed in use", "V",
        required=False, minimum=0, maximum=1000, placeholder="",
        help="If known, lets the safety checks test for over-discharge damage.",
    ),
    InputField(
        "measured_capacity_ah", "Measured capacity from a capacity test", "Ah",
        required=False, minimum=0.01, maximum=10000, placeholder="",
        help="Only if you have run a full controlled discharge. This is a "
             "MEASUREMENT, not an estimate, and is reported separately.",
    ),
]


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

TIER_1 = InputTier(
    key="telemetry_eis", rank=1,
    display_name="Charge telemetry with impedance diagnostics",
    description=(
        "A full charge curve (time, voltage, current, temperature) plus "
        "electrochemical impedance values. What a workshop with a bench cycler "
        "and EIS equipment can supply."
    ),
    source="telemetry",
    features=[
        "cc_capacity_frac", "cv_capacity_frac", "cc_cv_ah_ratio",
        "cc_time_fraction", "dvdt_cc_per_frac", "v_norm_at_cc_end",
        "ohmic_r_norm", "re_norm", "rct_norm",
        "ch_temp_max_c", "ch_temp_rise_c", "ch_temp_mean_c",
        "ch_thermal_dose_c_h", "ch_frac_above_warn", "ambient_temp_c",
    ],
)

TIER_2 = InputTier(
    key="telemetry", rank=2,
    display_name="Charge telemetry",
    description=(
        "A full charge curve with no impedance data. What a BMS log or a "
        "data-logging charger produces. This is the common case in the field, "
        "since production battery management systems almost never carry EIS "
        "hardware."
    ),
    source="telemetry",
    features=[
        "cc_capacity_frac", "cv_capacity_frac", "cc_cv_ah_ratio",
        "cc_time_fraction", "dvdt_cc_per_frac", "v_norm_at_cc_end",
        "ohmic_r_norm",
        "ch_temp_max_c", "ch_temp_rise_c", "ch_temp_mean_c",
        "ch_thermal_dose_c_h", "ch_frac_above_warn", "ambient_temp_c",
    ],
)

TIER_3 = InputTier(
    key="summary", rank=3,
    display_name="Charge summary (hand-entered)",
    description=(
        "Six numbers readable from a charger display, a BMS app and a clock. No "
        "instrumentation required. Costs only about 0.2 SOH points against a "
        "full instrumented charge curve, because the constant-current to "
        "constant-voltage split carries most of the signal and survives being "
        "reduced to a few typed figures."
    ),
    source="manual",
    features=[
        "cc_capacity_frac", "cv_capacity_frac", "cc_cv_ah_ratio",
        "cc_time_fraction", "ch_temp_max_c", "ambient_temp_c",
    ],
    fields=TIER3_FIELDS,
)

TIER_4 = InputTier(
    key="minimal", rank=4,
    display_name="Minimal (charge phase split only)",
    description=(
        "Only how the charge divided between its steady and tapering phases. "
        "Included for completeness and clearly marked indicative-only: measured "
        "R2 falls to 0.13 and the worst-case cell misses by 13 SOH points. No "
        "reuse grade is issued at this tier."
    ),
    source="manual",
    features=["cc_cv_ah_ratio", "cc_time_fraction"],
    reliable=False,
)

TIERS: Dict[str, InputTier] = {
    t.key: t for t in (TIER_1, TIER_2, TIER_3, TIER_4)}
TIER_ORDER: List[str] = [t.key for t in sorted(
    TIERS.values(), key=lambda t: t.rank)]


def get_tier(key: str) -> InputTier:
    if key not in TIERS:
        raise KeyError(
            f"Unknown input tier {key!r}. Known tiers: {TIER_ORDER}")
    return TIERS[key]


def best_tier_for(available: set) -> InputTier:
    """Selects the highest available input tier.

    Checks which features are provided by the user and chooses the most complete
    tier that can be used for assessment.
    """
    for key in TIER_ORDER:
        tier = TIERS[key]
        if all(f in available for f in tier.features):
            return tier
    return TIER_4


def questionnaire_schema() -> Dict:
    """Everything the frontend needs to render the manual-entry form."""
    return {
        "tiers": [TIERS[k].as_dict() for k in TIER_ORDER],
        "manual_tier": TIER_3.key,
        "context_fields": [f.as_dict() for f in CONTEXT_FIELDS],
    }
