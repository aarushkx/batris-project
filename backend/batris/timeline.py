"""
Battery health timeline.

The dashboard already answers "how healthy is this battery *now*". This module
answers the other half of the question a buyer, fleet operator or recycler
actually asks: *when did it get like this, and what happened on the way?*

It takes an assessment document exactly as produced by
:class:`~backend.batris.assess.BatteryAssessor` (or the unseen-battery
assessor) and folds the estimated SOH trajectory, the per-cycle anomaly
detections, the recorded thermal history and the present safety verdict into
one ordered list of dated events, plus the health *phases* those events divide
the life into.

Nothing here re-estimates anything. Every number in the timeline is taken from
the assessment it was handed, so the timeline can never disagree with the
dashboard or with a signed passport issued from the same assessment. That also
means this module works on a stored assessment snapshot (a marketplace
listing, a saved account record) with no models loaded at all.

Rules are deliberately explicit rather than learned: a state transition is a
statement about the battery's disposition, and a reader is entitled to know the
exact threshold that produced it.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Health states
# ---------------------------------------------------------------------------
# `state` is the fine-grained label (mirrors BatteryAssessor._health_label so
# the timeline and the dashboard never use different words for the same thing).
# `phase` is the coarse healthy / warning / critical band the feature brief
# asks for, and is what drives colour in the UI.

AS_NEW_SOH = 0.95
DEGRADED_SOH = 0.70          # boundary between reuse grades B and C
MILESTONE_SOH = 0.90         # "first tenth of the capacity is gone"

STATE_ORDER = ["as_new", "healthy", "degraded", "heavily_degraded", "end_of_life"]

STATE_META: Dict[str, Dict[str, str]] = {
    "as_new": {
        "label": "As-new",
        "phase": "healthy",
        "meaning": "Capacity is within a few points of nameplate.",
    },
    "healthy": {
        "label": "Healthy",
        "phase": "healthy",
        "meaning": "Above the end-of-first-life threshold; fit for its original duty.",
    },
    "degraded": {
        "label": "Degraded",
        "phase": "warning",
        "meaning": "Past first life, but retains ample capacity for stationary reuse.",
    },
    "heavily_degraded": {
        "label": "Heavily degraded",
        "phase": "warning",
        "meaning": "Approaching the reuse floor; only derated, attended duty is appropriate.",
    },
    "end_of_life": {
        "label": "End of usable life",
        "phase": "critical",
        "meaning": "Below the reuse floor; material recovery yields more value than reuse.",
    },
}

SEVERITY_ORDER = {"critical": 0, "warning": 1, "good": 2, "info": 3}

# How many consecutive cycles a new state must hold before the crossing is
# recorded. A model estimate wobbles by a point or two, and without this a
# battery sitting exactly on 80% would generate a dozen transitions that
# describe the estimator rather than the battery.
CONFIRM_RUN = 3

# Anomalous cycles this far apart or closer are reported as one episode.
CLUSTER_GAP = 3

# Matches safety._degradation_rate_risk: the point at which fade stops looking
# linear and starts looking like the ageing knee.
KNEE_FADE_POINTS_PER_100 = 3.0
KNEE_WINDOW = 30          # same trailing window assess._fade_slope uses
KNEE_SUSTAIN = 5          # cycles the elevated rate must hold before it counts


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _finite(value: Any) -> Optional[float]:
    """Coerce to a float, mapping None/NaN/inf/garbage to None."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pct(soh: Optional[float]) -> Optional[float]:
    return None if soh is None else round(100.0 * soh, 1)


def _state_for_soh(soh: float, eol: float, floor: float) -> str:
    if soh >= AS_NEW_SOH:
        return "as_new"
    if soh >= eol:
        return "healthy"
    if soh >= DEGRADED_SOH:
        return "degraded"
    if soh >= floor:
        return "heavily_degraded"
    return "end_of_life"


def _grade_for_soh(soh: float, eol: float, floor: float) -> str:
    """Mirror of safety._grade_for_soh, expressed against a format dict.

    Kept local so the timeline can be built from a stored assessment snapshot
    without loading the battery-format registry.
    """
    if soh >= eol:
        return "A"
    if soh >= DEGRADED_SOH:
        return "B"
    if soh >= floor:
        return "C"
    return "RECYCLE"


def _phase(state: str) -> str:
    return STATE_META[state]["phase"]


def _clusters(indices: Sequence[int], gap: int = CLUSTER_GAP) -> List[List[int]]:
    """Group sorted positions into runs separated by more than `gap`."""
    groups: List[List[int]] = []
    for index in sorted(indices):
        if groups and index - groups[-1][-1] <= gap:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def _smooth_states(states: Sequence[str], window: int = 5) -> List[str]:
    """Median-filter the state series on its natural ordinal scale.

    Health states are ordered, so a median is meaningful. This removes
    single-cycle flips caused by estimator noise before any transition is
    recorded — without it a battery sitting near a threshold produces events
    that describe the model rather than the cell.
    """
    if len(states) < window:
        return list(states)
    ranks = [STATE_ORDER.index(state) for state in states]
    half = window // 2
    out: List[str] = []
    for position in range(len(ranks)):
        lo = max(0, position - half)
        hi = min(len(ranks), position + half + 1)
        chunk = sorted(ranks[lo:hi])
        out.append(STATE_ORDER[chunk[len(chunk) // 2]])
    return out


def _fade_points_per_100(series: Sequence[float], end: int, window: int) -> Optional[float]:
    """Trailing fade rate in SOH points per 100 cycles at position `end`.

    Positive means losing health. Uses a least-squares slope over the trailing
    window, the same way assess._fade_slope does, so the number the timeline
    reports for "now" agrees with the number on the dashboard.
    """
    start = max(0, end - window + 1)
    chunk = [v for v in series[start:end + 1] if v is not None and math.isfinite(v)]
    if len(chunk) < 5:
        return None
    n = len(chunk)
    mean_x = (n - 1) / 2.0
    mean_y = sum(chunk) / n
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator <= 0:
        return None
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(chunk)) / denominator
    return -100.0 * 100.0 * slope


def _fmt_date(timestamp: Optional[str]) -> Optional[str]:
    """Normalise a cycle timestamp to an ISO date, or None if unusable."""
    if not timestamp:
        return None
    text = str(timestamp).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else text


# ---------------------------------------------------------------------------
# Event assembly
# ---------------------------------------------------------------------------

class _Builder:
    """Collects events, keeping ids stable and ordering deterministic."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def add(
        self,
        kind: str,
        title: str,
        detail: str,
        severity: str = "info",
        cycle: Optional[int] = None,
        date: Optional[str] = None,
        soh_percent: Optional[float] = None,
        phase: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.events.append(
            {
                "id": f"{kind}-{len(self.events)}",
                "kind": kind,
                "severity": severity,
                "title": title,
                "detail": detail,
                "cycle": cycle,
                "date": date,
                "soh_percent": soh_percent,
                "phase": phase,
                "evidence": evidence or {},
            }
        )

    def sorted_events(self) -> List[Dict[str, Any]]:
        # Chronological, with undated forward-looking entries (the projection)
        # pinned to the end; ties broken by severity so the most serious thing
        # that happened at a cycle is read first.
        return sorted(
            self.events,
            key=lambda e: (
                e["cycle"] is None,
                e["cycle"] if e["cycle"] is not None else 0,
                SEVERITY_ORDER.get(e["severity"], 9),
            ),
        )


def _state_runs(
    states: Sequence[str],
    cycles: Sequence[int],
) -> List[Tuple[int, int, str]]:
    """Confirmed state runs as (start position, end position, state).

    A candidate state has to hold for CONFIRM_RUN cycles before it replaces the
    running state; the tail is always accepted so the present state is never
    swallowed by the confirmation rule.
    """
    if not states:
        return []

    runs: List[Tuple[int, int, str]] = []
    current = states[0]
    current_start = 0
    candidate: Optional[str] = None
    candidate_start = 0

    for position in range(1, len(states)):
        state = states[position]
        if state == current:
            candidate = None
            continue

        if state != candidate:
            candidate = state
            candidate_start = position

        held = position - candidate_start + 1
        is_tail = position == len(states) - 1
        if held >= CONFIRM_RUN or (is_tail and held >= 1):
            runs.append((current_start, candidate_start - 1, current))
            current = candidate
            current_start = candidate_start
            candidate = None

    runs.append((current_start, len(states) - 1, current))
    return [run for run in runs if run[1] >= run[0]]


def _describe_transition(previous: str, nxt: str) -> Tuple[str, str]:
    """Severity and verb for a state transition."""
    worsened = STATE_ORDER.index(nxt) > STATE_ORDER.index(previous)
    if not worsened:
        return "good", "recovered to"
    phase = _phase(nxt)
    if phase == "critical":
        return "critical", "fell to"
    if phase == "warning":
        return "warning", "dropped to"
    return "info", "moved to"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_timeline(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one assessment document into a dated health timeline.

    Works in two modes:

    * **trajectory** — the assessment carries a per-cycle history (the dataset
      batteries), so real transitions, anomaly episodes and thermal excursions
      can be located in time.
    * **snapshot** — a single-cycle assessment of a user's own battery. There
      is no history to walk, so the timeline reports what the one observation
      establishes and says plainly that earlier life is unobserved.
    """
    if not isinstance(assessment, dict) or not assessment:
        raise ValueError("An assessment document is required to build a timeline.")

    health = assessment.get("health") or {}
    if not health:
        raise ValueError("Assessment has no health estimate; cannot build a timeline.")

    fmt = assessment.get("format") or {}
    safety = assessment.get("safety") or {}
    anomaly = assessment.get("anomaly") or {}
    second_life = assessment.get("second_life") or {}
    trajectory = assessment.get("trajectory") or {}

    battery_id = str(assessment.get("battery_id") or "Battery")
    eol = _finite(fmt.get("eol_soh")) or _finite(health.get("eol_threshold")) or 0.80
    floor = _finite(fmt.get("second_life_floor_soh")) or 0.60
    temp_warn = _finite(fmt.get("temp_warn_c"))

    soh_now = _finite(health.get("soh"))
    if soh_now is None:
        raise ValueError("Assessment health estimate has no SOH value.")

    builder = _Builder()

    cycles: List[int] = [int(c) for c in (trajectory.get("cycle_index") or [])]
    estimated: List[Optional[float]] = [
        _finite(v) for v in (trajectory.get("estimated_soh") or [])
    ]
    timestamps: List[Optional[str]] = list(trajectory.get("timestamp") or [])
    peak_temps: List[Optional[float]] = [
        _finite(v) for v in (trajectory.get("peak_temp_c") or [])
    ]
    anomalous_cycles = {int(c) for c in (trajectory.get("anomalous_cycles") or [])}

    has_history = len(cycles) >= 2 and any(v is not None for v in estimated)

    def date_at(position: int) -> Optional[str]:
        if 0 <= position < len(timestamps):
            return _fmt_date(timestamps[position])
        return None

    states: List[Dict[str, Any]] = []
    milestones_hit: List[Dict[str, Any]] = []

    if has_history:
        # ---------------------------------------------------------- history
        # Carry the last finite estimate forward so a single missing cycle
        # cannot invent a state transition.
        filled: List[float] = []
        last = next(v for v in estimated if v is not None)
        for value in estimated:
            last = value if value is not None else last
            filled.append(last)

        raw_states = [_state_for_soh(v, eol, floor) for v in filled]
        state_series = _smooth_states(raw_states)
        runs = _state_runs(state_series, cycles)

        # The median filter can nudge a transition a cycle or two ahead of the
        # actual crossing. Anchoring each run to the first cycle whose *raw*
        # estimate really is in that state keeps the quoted SOH consistent with
        # the state and the reuse grade it is reported alongside.
        anchored: List[Tuple[int, int, str]] = []
        for index, (start, end, state) in enumerate(runs):
            anchor = 0 if index == 0 else next(
                (p for p in range(start, end + 1) if raw_states[p] == state),
                start,
            )
            anchored.append((anchor, end, state))
        # Keep runs contiguous after anchoring.
        runs = [
            (start, anchored[i + 1][0] - 1 if i + 1 < len(anchored) else end, state)
            for i, (start, end, state) in enumerate(anchored)
        ]
        runs = [run for run in runs if run[1] >= run[0]]

        for index, (start, end, state) in enumerate(runs):
            meta = STATE_META[state]
            states.append(
                {
                    "state": state,
                    "label": meta["label"],
                    "phase": meta["phase"],
                    "meaning": meta["meaning"],
                    "from_cycle": cycles[start],
                    "to_cycle": cycles[end],
                    "duration_cycles": cycles[end] - cycles[start] + 1,
                    "entered_at_soh_percent": _pct(filled[start]),
                    "entered_on": date_at(start),
                    "reuse_grade": _grade_for_soh(filled[start], eol, floor),
                    "is_current": index == len(runs) - 1,
                }
            )

        # -- monitoring start ------------------------------------------------
        builder.add(
            "observation_start",
            "Monitoring began",
            f"First recorded cycle for {battery_id}. Estimated state of health "
            f"{_pct(filled[0]):.1f}% — {STATE_META[state_series[0]]['label'].lower()}.",
            severity="info",
            cycle=cycles[0],
            date=date_at(0),
            soh_percent=_pct(filled[0]),
            phase=_phase(state_series[0]),
            evidence={"reuse_grade": _grade_for_soh(filled[0], eol, floor)},
        )

        # -- state transitions ----------------------------------------------
        for index, (start, _end, state) in enumerate(runs[1:], start=1):
            previous = runs[index - 1][2]
            severity, verb = _describe_transition(previous, state)
            meta = STATE_META[state]
            grade = _grade_for_soh(filled[start], eol, floor)
            threshold = {
                "healthy": eol,
                "degraded": eol,
                "heavily_degraded": DEGRADED_SOH,
                "end_of_life": floor,
            }.get(state)
            boundary = (
                f" It crossed the {100 * threshold:.0f}% boundary at this point."
                if threshold is not None and state != "healthy"
                else ""
            )
            builder.add(
                "state_change",
                f"Condition {verb} {meta['label'].lower()}",
                f"Estimated health reached {_pct(filled[start]):.1f}% at cycle "
                f"{cycles[start]}, moving the battery from "
                f"{STATE_META[previous]['label'].lower()} to {meta['label'].lower()}. "
                f"{meta['meaning']} Reuse grade at this point: {grade}.{boundary}",
                severity=severity,
                cycle=cycles[start],
                date=date_at(start),
                soh_percent=_pct(filled[start]),
                phase=meta["phase"],
                evidence={
                    "from_state": previous,
                    "to_state": state,
                    "reuse_grade": grade,
                    "threshold_soh_percent": None if threshold is None else round(100 * threshold, 1),
                },
            )

        # -- the 90% milestone ----------------------------------------------
        # The state boundaries already cover 95 / 80 / 70 / 60, so only the
        # 90% mark needs an event of its own.
        for position, value in enumerate(filled):
            if value < MILESTONE_SOH:
                if position > 0 and filled[0] >= MILESTONE_SOH:
                    milestones_hit.append({"soh_percent": 90.0, "cycle": cycles[position]})
                    builder.add(
                        "milestone",
                        "Health passed below 90%",
                        f"Estimated health crossed the 90% mark at cycle {cycles[position]}. "
                        "Fade of this size is normal for a lithium-ion cell and is driven "
                        "mostly by solid-electrolyte-interphase growth rather than by a "
                        "fault. Recorded history for this cell begins at "
                        f"{_pct(filled[0]):.1f}%, so any earlier loss is outside the "
                        "observed window.",
                        severity="info",
                        cycle=cycles[position],
                        date=date_at(position),
                        soh_percent=_pct(value),
                        phase=_phase(_state_for_soh(value, eol, floor)),
                    )
                break

        # -- ageing knee -----------------------------------------------------
        # An absolute threshold alone is not enough: some cells fade quickly
        # from the first cycle, and calling that a "knee" would be wrong. The
        # knee is where fade accelerates against *this cell's own* early-life
        # rate, so the baseline is measured over the first third of its life.
        baseline_end = max(KNEE_WINDOW, len(filled) // 3)
        baseline = _fade_points_per_100(filled, min(baseline_end, len(filled) - 1), baseline_end)
        if baseline is not None:
            trigger = max(
                KNEE_FADE_POINTS_PER_100,
                1.6 * baseline if baseline > 0 else KNEE_FADE_POINTS_PER_100,
                baseline + 2.0,
            )
            sustained = 0
            for position in range(baseline_end, len(filled)):
                rate = _fade_points_per_100(filled, position, KNEE_WINDOW)
                if rate is not None and rate >= trigger:
                    sustained += 1
                else:
                    sustained = 0
                if sustained < KNEE_SUSTAIN:
                    continue
                onset = position - KNEE_SUSTAIN + 1
                builder.add(
                    "fade_acceleration",
                    "Fade rate accelerated",
                    f"From around cycle {cycles[onset]} the trailing fade rate reached "
                    f"{rate:.1f} SOH points per 100 cycles, against {baseline:.1f} points "
                    "per 100 cycles over this cell's early life. Degradation past this "
                    "point is less predictable and is associated with lithium plating, "
                    "so inspection intervals should shorten from here.",
                    severity="warning",
                    cycle=cycles[onset],
                    date=date_at(onset),
                    soh_percent=_pct(filled[onset]),
                    phase=_phase(state_series[onset]),
                    evidence={
                        "fade_points_per_100_cycles": round(rate, 2),
                        "early_life_points_per_100_cycles": round(baseline, 2),
                        "trigger_points_per_100_cycles": round(trigger, 2),
                    },
                )
                break

        # -- anomaly episodes ------------------------------------------------
        anomalous_positions = [
            position for position, cycle in enumerate(cycles) if cycle in anomalous_cycles
        ]
        if anomalous_positions:
            first = anomalous_positions[0]
            builder.add(
                "anomaly_first",
                "First anomalous cycle",
                f"Cycle {cycles[first]} is the earliest cycle flagged by the anomaly "
                "detectors. Ordinary capacity fade is not flagged, so a detection here "
                "means the cycle itself behaved unlike the rest of this battery's history.",
                severity="warning",
                cycle=cycles[first],
                date=date_at(first),
                soh_percent=_pct(filled[first]),
                phase=_phase(state_series[first]),
            )

            episodes = _clusters(anomalous_positions)
            # Keep the timeline readable: report the largest episodes, then put
            # them back in cycle order.
            ranked = sorted(episodes, key=len, reverse=True)[:8]
            for episode in sorted(ranked, key=lambda group: group[0]):
                if len(episode) < 2:
                    continue
                start, end = episode[0], episode[-1]
                span = (
                    f"cycle {cycles[start]}"
                    if start == end
                    else f"cycles {cycles[start]}\u2013{cycles[end]}"
                )
                builder.add(
                    "anomaly_cluster",
                    f"{len(episode)} anomalous cycles in a row",
                    f"A cluster of {len(episode)} flagged cycles at {span}. Clustered "
                    "detections are more informative than isolated ones: a run of "
                    "abnormal cycles usually means a persistent physical change rather "
                    "than a single bad measurement.",
                    severity="critical" if len(episode) >= 5 else "warning",
                    cycle=cycles[start],
                    date=date_at(start),
                    soh_percent=_pct(filled[start]),
                    phase=_phase(state_series[start]),
                    evidence={
                        "cycles_flagged": len(episode),
                        "from_cycle": cycles[start],
                        "to_cycle": cycles[end],
                    },
                )

        # -- thermal history -------------------------------------------------
        if temp_warn is not None and any(t is not None for t in peak_temps):
            hot = [
                position
                for position, temp in enumerate(peak_temps)
                if temp is not None and temp >= temp_warn
            ]

            if not hot:
                # Silence from a check and absence of a check are different
                # results, so the clean case is stated rather than omitted.
                hottest = max(
                    (position for position, temp in enumerate(peak_temps) if temp is not None),
                    key=lambda position: peak_temps[position],
                )
                builder.add(
                    "thermal_clear",
                    "Hottest cycle stayed inside the advisory limit",
                    f"The warmest cycle on record is cycle {cycles[hottest]} at "
                    f"{peak_temps[hottest]:.1f} \u00b0C, against a {temp_warn:.0f} \u00b0C "
                    "advisory limit for this format. No cycle in the observed history "
                    "exceeded it, so thermal stress is not a contributor to the fade "
                    "shown here.",
                    severity="good",
                    cycle=cycles[hottest],
                    date=date_at(hottest),
                    soh_percent=_pct(filled[hottest]),
                    phase=_phase(state_series[hottest]),
                    evidence={
                        "peak_temp_c": round(peak_temps[hottest] or 0.0, 1),
                        "advisory_limit_c": temp_warn,
                    },
                )

            for episode in sorted(_clusters(hot), key=len, reverse=True)[:3]:
                start, end = episode[0], episode[-1]
                peak = max(peak_temps[p] or 0.0 for p in episode)
                span = (
                    f"cycle {cycles[start]}"
                    if start == end
                    else f"cycles {cycles[start]}\u2013{cycles[end]}"
                )
                builder.add(
                    "thermal_excursion",
                    "Temperature above the advisory limit",
                    f"Peak cell temperature reached {peak:.1f} \u00b0C at {span}, above the "
                    f"{temp_warn:.0f} \u00b0C advisory limit for this format. Degradation rate "
                    "roughly doubles for every 10 \u00b0C rise, so time spent here is "
                    "disproportionately expensive in capacity.",
                    severity="warning",
                    cycle=cycles[start],
                    date=date_at(start),
                    soh_percent=_pct(filled[start]),
                    phase=_phase(state_series[start]),
                    evidence={
                        "peak_temp_c": round(peak, 1),
                        "advisory_limit_c": temp_warn,
                        "cycles_affected": len(episode),
                    },
                )

    else:
        # ---------------------------------------------------------- snapshot
        state = _state_for_soh(soh_now, eol, floor)
        meta = STATE_META[state]
        states.append(
            {
                "state": state,
                "label": meta["label"],
                "phase": meta["phase"],
                "meaning": meta["meaning"],
                "from_cycle": assessment.get("cycle_index"),
                "to_cycle": assessment.get("cycle_index"),
                "duration_cycles": None,
                "entered_at_soh_percent": _pct(soh_now),
                "entered_on": None,
                "reuse_grade": _grade_for_soh(soh_now, eol, floor),
                "is_current": True,
            }
        )
        builder.add(
            "unobserved_history",
            "Earlier life not observed",
            "This battery was assessed from a single charge observation, so nothing "
            "before that point can be dated. The timeline therefore starts at the "
            "assessment itself. Supplying a per-cycle log would let the platform place "
            "the transitions below in time.",
            severity="info",
            cycle=None,
            phase="healthy",
        )

    # ------------------------------------------------------------- present
    assessed_cycle = assessment.get("cycle_index")
    assessed_cycle = int(assessed_cycle) if isinstance(assessed_cycle, (int, float)) else None
    current_state = _state_for_soh(soh_now, eol, floor)
    risk_band = str(safety.get("risk_band") or "UNKNOWN")
    interval = health.get("confidence_interval_90") or []
    interval_text = ""
    if len(interval) == 2:
        low, high = _finite(interval[0]), _finite(interval[1])
        if low is not None and high is not None:
            interval_text = f" 90% confidence interval {100 * low:.1f}\u2013{100 * high:.1f}%."

    assessed_position = cycles.index(assessed_cycle) if (assessed_cycle in cycles) else None
    grade_now = second_life.get("grade") or "not graded"

    builder.add(
        "assessment",
        "Present assessment",
        f"Estimated state of health {_pct(soh_now):.1f}% ({STATE_META[current_state]['label']}), "
        f"safety risk band {risk_band}, reuse grade {grade_now}."
        f"{interval_text} {second_life.get('recommendation', '')}".strip(),
        severity=(
            "critical" if risk_band == "HIGH"
            else "warning" if risk_band in {"ELEVATED", "MODERATE"}
            else "good"
        ),
        cycle=assessed_cycle,
        date=date_at(assessed_position) if assessed_position is not None else None,
        soh_percent=_pct(soh_now),
        phase=_phase(current_state),
        evidence={
            "risk_score": _finite(safety.get("risk_score")),
            "reuse_grade": second_life.get("grade"),
            "grade_confidence": second_life.get("grade_confidence"),
        },
    )

    # Dominant degradation mechanism at the assessed cycle.
    factors = assessment.get("degradation_factors") or []
    if factors:
        top = factors[0]
        share = _finite(top.get("share_of_explanation"))
        share_text = f" It accounts for {100 * share:.0f}% of the explained fade." if share else ""
        builder.add(
            "degradation_attribution",
            f"Dominant mechanism: {top.get('label', top.get('factor', 'unknown'))}",
            f"{top.get('narrative') or top.get('mechanism') or ''}{share_text}".strip(),
            severity="info",
            cycle=assessed_cycle,
            date=date_at(assessed_position) if assessed_position is not None else None,
            soh_percent=_pct(soh_now),
            phase=_phase(current_state),
            evidence={"share_of_explanation": share},
        )

    # Live anomaly findings at the assessed cycle.
    for item in (anomaly.get("anomalies") or []):
        severity = str(item.get("severity") or "info")
        code = str(item.get("code") or "anomaly")
        # Detector codes are SCREAMING_SNAKE_CASE. They read badly in a
        # sentence and cannot be wrapped in a narrow PDF column, so the
        # human form goes in the title and the literal code in the evidence.
        readable = code.replace("_", " ").capitalize()
        builder.add(
            "anomaly_finding",
            f"Active detection: {readable}",
            str(item.get("detail") or ""),
            severity="critical" if severity == "critical" else
                     "warning" if severity == "warning" else "info",
            cycle=assessed_cycle,
            date=date_at(assessed_position) if assessed_position is not None else None,
            soh_percent=_pct(soh_now),
            phase=_phase(current_state),
            evidence={
                "code": code,
                "source": item.get("source"),
                **(item.get("evidence") or {}),
            },
        )

    # ---------------------------------------------------------- projection
    fade_now = _finite(health.get("fade_rate_soh_points_per_100_cycles"))
    projection: Optional[Dict[str, Any]] = None
    if fade_now is not None and fade_now > 0.05:
        targets: List[Tuple[str, float]] = []
        if soh_now > eol:
            targets.append(("end of first life", eol))
        if soh_now > floor:
            targets.append(("the reuse floor", floor))
        if targets:
            label, target = targets[0]
            remaining_points = 100.0 * (soh_now - target)
            cycles_left = int(round(100.0 * remaining_points / fade_now))
            projection = {
                "target_label": label,
                "target_soh_percent": round(100 * target, 1),
                "fade_points_per_100_cycles": round(fade_now, 2),
                "cycles_remaining": cycles_left,
                "reference_cycle": assessed_cycle,
            }
            builder.add(
                "projection",
                f"Projected to reach {label} in about {cycles_left} cycles",
                f"At the current fade rate of {fade_now:.2f} SOH points per 100 cycles, "
                f"{remaining_points:.1f} points of margin remain before "
                f"{100 * target:.0f}%. This is a straight-line extrapolation of the recent "
                "trend, not a prognostic model: fade usually accelerates near end of life, "
                "so treat this as an upper bound on remaining service.",
                severity="info",
                cycle=None,
                soh_percent=_pct(target),
                phase=_phase(_state_for_soh(target, eol, floor)),
                evidence=projection,
            )

    # ------------------------------------------------------------- summary
    events = builder.sorted_events()
    dated = [event for event in events if event["cycle"] is not None]

    first_soh = states[0]["entered_at_soh_percent"] if states else _pct(soh_now)
    current = next((state for state in states if state.get("is_current")), None)

    lost = None
    if first_soh is not None:
        lost = round(first_soh - (_pct(soh_now) or 0.0), 1)

    if has_history and current is not None:
        cycles_in_state = (cycles[-1] - current["from_cycle"] + 1) if current["from_cycle"] is not None else None
    else:
        cycles_in_state = None

    headline_parts = [
        f"{battery_id} has been observed for {len(cycles)} cycles"
        if has_history else f"{battery_id} was assessed from a single observation",
    ]
    if lost is not None and lost > 0 and has_history:
        headline_parts.append(f"losing {lost:.1f} SOH points over that span")
    headline_parts.append(
        f"and is currently {STATE_META[current_state]['label'].lower()} "
        f"at {_pct(soh_now):.1f}%"
    )
    headline = ", ".join(headline_parts[:-1]) + " " + headline_parts[-1] + "."

    summary = {
        "battery_id": battery_id,
        "source": "trajectory" if has_history else "snapshot",
        "cycles_observed": len(cycles) if has_history else assessment.get("total_cycles_observed"),
        "first_cycle": cycles[0] if has_history else None,
        "last_cycle": cycles[-1] if has_history else None,
        "assessed_at_cycle": assessed_cycle,
        "soh_at_first_observation_percent": first_soh if has_history else None,
        "soh_now_percent": _pct(soh_now),
        "soh_points_lost": lost if has_history else None,
        "fade_rate_soh_points_per_100_cycles": fade_now,
        "current_state": current_state,
        "current_state_label": STATE_META[current_state]["label"],
        "current_phase": _phase(current_state),
        "cycles_in_current_state": cycles_in_state,
        "reuse_grade": second_life.get("grade"),
        "risk_band": risk_band,
        "n_events": len(events),
        "n_state_changes": max(0, len(states) - 1),
        "n_warnings": sum(1 for event in events if event["severity"] == "warning"),
        "n_critical": sum(1 for event in events if event["severity"] == "critical"),
        "n_anomalous_cycles": len(anomalous_cycles),
        "first_event_date": next((e["date"] for e in dated if e["date"]), None),
        "last_event_date": next((e["date"] for e in reversed(dated) if e["date"]), None),
        "headline": headline,
        "projection": projection,
    }

    return {
        "battery_id": battery_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "format": {
            "key": fmt.get("key"),
            "display_name": fmt.get("display_name"),
            "chemistry": fmt.get("chemistry"),
            "rated_capacity_ah": _finite(fmt.get("rated_capacity_ah")),
            "eol_soh_percent": round(100 * eol, 1),
            "second_life_floor_soh_percent": round(100 * floor, 1),
        },
        "summary": summary,
        "states": states,
        "events": events,
        "series": {
            "cycle_index": cycles,
            "estimated_soh": [v for v in estimated],
            "measured_soh": [_finite(v) for v in (trajectory.get("measured_soh") or [])],
            "anomalous_cycles": sorted(anomalous_cycles),
            "method": trajectory.get("method"),
        } if has_history else None,
        "thresholds": {
            "as_new_soh_percent": round(100 * AS_NEW_SOH, 1),
            "eol_soh_percent": round(100 * eol, 1),
            "grade_b_floor_soh_percent": round(100 * DEGRADED_SOH, 1),
            "reuse_floor_soh_percent": round(100 * floor, 1),
        },
        "method_note": (
            "Every figure in this timeline is taken from the assessment it was built "
            "from; nothing is re-estimated here. State changes follow the format's "
            "defined thresholds and are confirmed over "
            f"{CONFIRM_RUN} consecutive cycles, preventing small model fluctuations "
            "from causing false events."
        ),
    }
