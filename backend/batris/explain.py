"""
Converts model feature importance values into simple degradation explanations.

Raw SHAP values only show how the model makes predictions, so this module
groups them into physical battery degradation factors and explains their impact
in a way that is easier for users to understand.

The explanations describe model patterns, not proven causes. Therefore, the
language focuses on what the model associates with degradation rather than
claiming direct cause and effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .features import FEATURE_LABELS, GROUP_DESCRIPTIONS, feature_group_of

EXPLANATION_CAVEAT = (
    "Degradation factors are derived from model attributions on observed "
    "telemetry. They identify which measured signals drive this estimate, and "
    "are not a certified root-cause determination."
)

#: Display names for the degradation mechanisms.
GROUP_LABELS: Dict[str, str] = {
    "charge_acceptance": "Loss of lithium inventory (charge acceptance)",
    "internal_resistance": "Internal resistance growth",
    "thermal_stress": "Thermal stress",
    "usage_history": "Cyclic and calendar ageing",
    "other": "Other factors",
}


@dataclass
class DegradationFactor:
    """One ranked degradation mechanism."""

    group: str
    label: str
    contribution: float          # signed, in SOH units
    contribution_pp: float       # signed, in SOH percentage points
    share: float                 # fraction of total explained magnitude, 0-1
    direction: str               # "reduces" | "supports"
    mechanism: str               # physical description
    top_signals: List[Dict] = field(default_factory=list)
    narrative: str = ""

    def as_dict(self) -> Dict:
        return {
            "factor": self.group,
            "label": self.label,
            "impact_soh_percentage_points": round(self.contribution_pp, 2),
            "share_of_explanation": round(self.share, 3),
            "direction": self.direction,
            "mechanism": self.mechanism,
            "narrative": self.narrative,
            "top_signals": self.top_signals,
        }


def _describe_signal(feature: str, value: float, contribution: float) -> Dict:
    return {
        "signal": FEATURE_LABELS.get(feature, feature),
        "feature": feature,
        "measured_value": None if value is None or not np.isfinite(value)
        else round(float(value), 4),
        "impact_soh_percentage_points": round(100 * contribution, 3),
    }


def explain_prediction(
    contributions: Dict[str, float],
    feature_values: Dict[str, float] | None = None,
    top_k: int = 4,
) -> List[DegradationFactor]:
    """Ranks the main degradation factors for a battery cycle.

    Uses SHAP values to show which features affect the SOH prediction the most.
    Negative values indicate factors reducing estimated health, while positive
    values indicate factors improving it.

    Factors are ranked by their impact so both harmful and helpful conditions are
    visible.
    """
    feature_values = feature_values or {}

    grouped: Dict[str, float] = {}
    per_group_features: Dict[str, List[tuple]] = {}
    for feature, value in contributions.items():
        group = feature_group_of(feature)
        grouped[group] = grouped.get(group, 0.0) + value
        per_group_features.setdefault(group, []).append((feature, value))

    total_magnitude = sum(abs(v) for v in grouped.values()) or 1.0

    factors: List[DegradationFactor] = []
    for group, contribution in grouped.items():
        signals = sorted(
            per_group_features[group], key=lambda kv: abs(kv[1]), reverse=True)
        top_signals = [
            _describe_signal(name, feature_values.get(name), value)
            for name, value in signals[:3]
            if abs(value) > 1e-6
        ]

        direction = "reduces" if contribution < 0 else "supports"
        contribution_pp = 100 * contribution
        share = abs(contribution) / total_magnitude

        if abs(contribution_pp) < 0.05:
            narrative = (
                f"{GROUP_LABELS.get(group, group)} is not materially influencing "
                "this estimate."
            )
        elif direction == "reduces":
            narrative = (
                f"{GROUP_LABELS.get(group, group)} accounts for about "
                f"{abs(contribution_pp):.1f} SOH percentage points of lost health "
                f"in this estimate ({100 * share:.0f}% of the total explanation)."
            )
        else:
            narrative = (
                f"{GROUP_LABELS.get(group, group)} is more favourable than the "
                f"fleet average, adding about {contribution_pp:.1f} SOH percentage "
                "points relative to a typical cell."
            )

        factors.append(DegradationFactor(
            group=group,
            label=GROUP_LABELS.get(group, group),
            contribution=contribution,
            contribution_pp=contribution_pp,
            share=share,
            direction=direction,
            mechanism=GROUP_DESCRIPTIONS.get(group, ""),
            top_signals=top_signals,
            narrative=narrative,
        ))

    factors.sort(key=lambda f: abs(f.contribution), reverse=True)
    return factors[:top_k]


def summarise_factors(factors: List[DegradationFactor]) -> str:
    """One-paragraph summary of the dominant degradation drivers."""
    harmful = [f for f in factors if f.direction ==
               "reduces" and abs(f.contribution_pp) >= 0.05]
    if not harmful:
        return (
            "No single degradation mechanism dominates this estimate; the cell is "
            "ageing in line with normal expectations for its usage."
        )

    lead = harmful[0]
    text = (
        f"The dominant degradation driver is {lead.label.lower()}, responsible for "
        f"roughly {abs(lead.contribution_pp):.1f} SOH percentage points "
        f"({100 * lead.share:.0f}% of the explained change)."
    )
    if len(harmful) > 1:
        second = harmful[1]
        text += (
            f" {second.label} is the next largest contributor at "
            f"{abs(second.contribution_pp):.1f} points."
        )
    return text
