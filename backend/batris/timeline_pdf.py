"""Renders a battery health timeline as a printable PDF.

This is layout only. It reads the timeline document produced by
:mod:`backend.batris.timeline` and prints it; it never recomputes a health
figure, so the PDF, the dashboard and any passport issued from the same
assessment always carry identical numbers.

The palette deliberately mirrors the web interface, including the rule that
severity colour is meaningful rather than decorative.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence

from reportlab.graphics.shapes import Drawing, Line, PolyLine, String, Rect, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------
# Palette — same tokens as frontend/src/app/globals.css
# --------------------------------------------------------------------------

INK = colors.HexColor("#0c1013")
INK_SOFT = colors.HexColor("#5b6560")
LINE = colors.HexColor("#e4e6e2")
MIST = colors.HexColor("#f4f5f3")
SIGNAL = colors.HexColor("#1b3fe0")
ESTIMATED = colors.HexColor("#6b4be0")
GOOD = colors.HexColor("#1f8a4c")
WARN = colors.HexColor("#b4740e")
BAD = colors.HexColor("#c4321f")

SEVERITY_COLOUR = {
    "critical": BAD,
    "warning": WARN,
    "good": GOOD,
    "info": INK_SOFT,
}

SEVERITY_LABEL = {
    "critical": "CRITICAL",
    "warning": "WARNING",
    "good": "CLEAR",
    "info": "INFO",
}

PHASE_COLOUR = {
    "healthy": GOOD,
    "warning": WARN,
    "critical": BAD,
}

_STYLES = getSampleStyleSheet()

_TITLE = ParagraphStyle(
    "TlTitle", parent=_STYLES["Heading1"], fontSize=18, leading=21,
    spaceAfter=2, textColor=INK,
)
_SUB = ParagraphStyle(
    "TlSub", parent=_STYLES["Normal"], fontSize=9, leading=12,
    textColor=INK_SOFT, spaceAfter=10,
)
_H2 = ParagraphStyle(
    "TlH2", parent=_STYLES["Heading2"], fontSize=11.5, leading=14,
    spaceBefore=14, spaceAfter=6, textColor=INK,
)
_BODY = ParagraphStyle(
    "TlBody", parent=_STYLES["Normal"], fontSize=9.3, leading=13,
    alignment=TA_LEFT, textColor=INK,
)
_SMALL = ParagraphStyle(
    "TlSmall", parent=_STYLES["Normal"], fontSize=8, leading=11,
    textColor=INK_SOFT,
)
_CELL = ParagraphStyle(
    "TlCell", parent=_STYLES["Normal"], fontSize=8.2, leading=11, textColor=INK,
)
_CELL_SOFT = ParagraphStyle(
    "TlCellSoft", parent=_STYLES["Normal"], fontSize=8, leading=10.8,
    textColor=INK_SOFT,
)
_HEAD = ParagraphStyle(
    "TlHead", parent=_STYLES["Normal"], fontSize=7.4, leading=9,
    textColor=INK_SOFT, fontName="Helvetica-Bold",
)
_HEADLINE = ParagraphStyle(
    "TlHeadline", parent=_STYLES["Normal"], fontSize=10.4, leading=14.5,
    textColor=INK,
)
_NOTE = ParagraphStyle(
    "TlNote", parent=_STYLES["Normal"], fontSize=7.8, leading=11,
    textColor=INK_SOFT,
)

CONTENT_WIDTH = A4[0] - 36 * mm


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _esc(value: Any) -> str:
    """Escape the three characters reportlab's mini-HTML cares about."""
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _num(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "\u2014"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _stamp(value: Optional[str]) -> str:
    if not value:
        return "\u2014"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return str(value)


def _date(value: Optional[str]) -> str:
    if not value:
        return "\u2014"
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except ValueError:
        return str(value)


def _metric_row(items: Sequence[tuple[str, str]]) -> Table:
    """A row of boxed headline figures, like the dashboard metric cards."""
    cells = [
        [
            Paragraph(_esc(label).upper(), _HEAD),
            Paragraph(f"<font size=13 color='#0c1013'><b>{_esc(value)}</b></font>", _BODY),
        ]
        for label, value in items
    ]
    inner = [
        Table([[cell[0]], [cell[1]]], colWidths=[CONTENT_WIDTH / len(cells) - 4])
        for cell in cells
    ]
    for block in inner:
        block.setStyle(
            TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, -1), (-1, -1), 0),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ])
        )
    outer = Table([inner], colWidths=[CONTENT_WIDTH / len(cells)] * len(cells))
    outer.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    return outer


def _kv_table(rows: Sequence[tuple[str, Any]]) -> Table:
    data = [
        [Paragraph(f"<b>{_esc(key)}</b>", _CELL), Paragraph(_esc(value), _CELL)]
        for key, value in rows
    ]
    table = Table(data, colWidths=[52 * mm, CONTENT_WIDTH - 52 * mm])
    table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ])
    )
    return table


# --------------------------------------------------------------------------
# SOH chart
# --------------------------------------------------------------------------

def _soh_chart(timeline: Dict[str, Any]) -> Optional[Drawing]:
    """Draw the estimated-SOH curve with state bands and threshold lines."""
    series = timeline.get("series") or {}
    cycles: List[int] = [int(c) for c in (series.get("cycle_index") or [])]
    estimated = [v for v in (series.get("estimated_soh") or [])]
    if len(cycles) < 2:
        return None

    points = [(c, v) for c, v in zip(cycles, estimated) if v is not None]
    if len(points) < 2:
        return None

    width = CONTENT_WIDTH
    height = 132.0
    pad_left, pad_right, pad_top, pad_bottom = 34.0, 12.0, 12.0, 22.0
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    x_min, x_max = points[0][0], points[-1][0]
    thresholds = timeline.get("thresholds") or {}
    eol = (thresholds.get("eol_soh_percent") or 80.0) / 100.0
    floor = (thresholds.get("reuse_floor_soh_percent") or 60.0) / 100.0
    grade_b = (thresholds.get("grade_b_floor_soh_percent") or 70.0) / 100.0

    values = [v for _c, v in points] + [eol, floor]
    y_min = max(0.0, min(values) - 0.03)
    y_max = min(1.05, max(values) + 0.03)

    def sx(cycle: float) -> float:
        return pad_left + (cycle - x_min) / max(1, x_max - x_min) * plot_w

    def sy(value: float) -> float:
        return pad_bottom + (value - y_min) / max(1e-6, y_max - y_min) * plot_h

    drawing = Drawing(width, height)

    # Health-phase bands, so the reader sees the same colour language as the
    # timeline entries below.
    bands = [
        (max(y_min, eol), y_max, GOOD),
        (max(y_min, floor), min(y_max, eol), WARN),
        (y_min, min(y_max, floor), BAD),
    ]
    for low, high, colour in bands:
        if high <= low:
            continue
        drawing.add(
            Rect(
                pad_left, sy(low), plot_w, sy(high) - sy(low),
                fillColor=colour, fillOpacity=0.06, strokeColor=None,
            )
        )

    # Gridlines and y labels.
    for step in range(5):
        value = y_min + step / 4 * (y_max - y_min)
        drawing.add(
            Line(pad_left, sy(value), pad_left + plot_w, sy(value),
                 strokeColor=LINE, strokeWidth=0.5)
        )
        drawing.add(
            String(pad_left - 5, sy(value) - 2.6, f"{100 * value:.0f}%",
                   fontName="Helvetica", fontSize=6.6, fillColor=INK_SOFT,
                   textAnchor="end")
        )

    # Threshold markers.
    for value, label, colour in (
        (eol, "80% end of first life", INK_SOFT),
        (grade_b, "70% grade B floor", INK_SOFT),
        (floor, "60% reuse floor", INK_SOFT),
    ):
        if not (y_min <= value <= y_max):
            continue
        drawing.add(
            Line(pad_left, sy(value), pad_left + plot_w, sy(value),
                 strokeColor=colour, strokeWidth=0.7, strokeDashArray=[3, 2])
        )
        drawing.add(
            String(pad_left + plot_w, sy(value) + 2.4, label,
                   fontName="Helvetica", fontSize=6, fillColor=INK_SOFT,
                   textAnchor="end")
        )

    # The curve.
    flat: List[float] = []
    for cycle, value in points:
        flat.extend([sx(cycle), sy(value)])
    drawing.add(PolyLine(flat, strokeColor=ESTIMATED, strokeWidth=1.5))

    # Event markers on the curve, coloured by severity.
    lookup = {c: v for c, v in points}
    for event in timeline.get("events") or []:
        cycle = event.get("cycle")
        if cycle is None or cycle not in lookup:
            continue
        if event.get("severity") not in {"critical", "warning"}:
            continue
        drawing.add(
            Circle(
                sx(cycle), sy(lookup[cycle]), 2.1,
                fillColor=SEVERITY_COLOUR[event["severity"]],
                strokeColor=colors.white, strokeWidth=0.5,
            )
        )

    # Axes.
    drawing.add(Line(pad_left, pad_bottom, pad_left + plot_w, pad_bottom,
                     strokeColor=LINE, strokeWidth=0.8))
    for step in range(6):
        cycle = x_min + step / 5 * (x_max - x_min)
        drawing.add(
            String(sx(cycle), pad_bottom - 9, f"{cycle:.0f}",
                   fontName="Helvetica", fontSize=6.6, fillColor=INK_SOFT,
                   textAnchor="middle")
        )
    drawing.add(
        String(pad_left + plot_w / 2, 3, "Cycle number",
               fontName="Helvetica", fontSize=6.6, fillColor=INK_SOFT,
               textAnchor="middle")
    )
    return drawing


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def _phase_table(timeline: Dict[str, Any]) -> Optional[Table]:
    states = timeline.get("states") or []
    if not states:
        return None

    header = [
        Paragraph("PHASE", _HEAD),
        Paragraph("CYCLES", _HEAD),
        Paragraph("ENTERED", _HEAD),
        Paragraph("SOH ON ENTRY", _HEAD),
        Paragraph("GRADE", _HEAD),
        Paragraph("WHAT IT MEANS", _HEAD),
    ]
    rows = [header]
    for state in states:
        span = (
            f"{state.get('from_cycle')}\u2013{state.get('to_cycle')}"
            if state.get("from_cycle") is not None
            else "\u2014"
        )
        label = state.get("label", "")
        if state.get("is_current"):
            label = f"{label} (current)"
        rows.append([
            Paragraph(f"<b>{_esc(label)}</b>", _CELL),
            Paragraph(_esc(span), _CELL),
            Paragraph(_date(state.get("entered_on")), _CELL_SOFT),
            Paragraph(_num(state.get("entered_at_soh_percent"), 1, "%"), _CELL),
            Paragraph(_esc(state.get("reuse_grade")), _CELL),
            Paragraph(_esc(state.get("meaning")), _CELL_SOFT),
        ])

    widths = [30 * mm, 16 * mm, 21 * mm, 19 * mm, 15 * mm]
    widths.append(CONTENT_WIDTH - sum(widths))
    table = Table(rows, colWidths=widths, repeatRows=1)

    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), MIST),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]
    for index, state in enumerate(states, start=1):
        colour = PHASE_COLOUR.get(state.get("phase", "healthy"), INK_SOFT)
        style.append(("LINEBEFORE", (0, index), (0, index), 2.2, colour))
    table.setStyle(TableStyle(style))
    return table


def _event_table(timeline: Dict[str, Any]) -> LongTable:
    header = [
        Paragraph("CYCLE", _HEAD),
        Paragraph("DATE", _HEAD),
        Paragraph("SEVERITY", _HEAD),
        Paragraph("EVENT", _HEAD),
        Paragraph("WHAT HAPPENED AND WHY IT MATTERS", _HEAD),
    ]
    rows = [header]
    events = timeline.get("events") or []
    for event in events:
        severity = str(event.get("severity") or "info")
        cycle = event.get("cycle")
        hex_colour = "#" + SEVERITY_COLOUR.get(severity, INK_SOFT).hexval()[2:]
        rows.append([
            Paragraph("\u2014" if cycle is None else f"<b>{cycle}</b>", _CELL),
            Paragraph(_date(event.get("date")), _CELL_SOFT),
            Paragraph(
                f'<font color="{hex_colour}"><b>'
                f'{SEVERITY_LABEL.get(severity, "INFO")}</b></font>',
                _CELL_SOFT,
            ),
            Paragraph(f"<b>{_esc(event.get('title'))}</b>", _CELL),
            Paragraph(_esc(event.get("detail")), _CELL_SOFT),
        ])

    widths = [15 * mm, 20 * mm, 21 * mm, 38 * mm]
    widths.append(CONTENT_WIDTH - sum(widths))
    table = LongTable(rows, colWidths=widths, repeatRows=1)

    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), MIST),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
    ]
    for index, event in enumerate(events, start=1):
        colour = SEVERITY_COLOUR.get(str(event.get("severity")), INK_SOFT)
        style.append(("LINEBEFORE", (0, index), (0, index), 2.2, colour))
    table.setStyle(TableStyle(style))
    return table


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def render_timeline_pdf(timeline: Dict[str, Any]) -> bytes:
    """Render a timeline document (from timeline.build_timeline) to PDF bytes."""
    if not isinstance(timeline, dict) or not timeline.get("summary"):
        raise ValueError("A timeline document is required.")

    summary = timeline.get("summary") or {}
    fmt = timeline.get("format") or {}
    battery_id = timeline.get("battery_id", "Battery")
    snapshot = summary.get("source") != "trajectory"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Battery health timeline {battery_id}",
        author="BATRIS",
        subject="Battery health timeline",
    )

    story: List[Any] = [
        Paragraph("Battery health timeline", _TITLE),
        Paragraph(
            f"{_esc(battery_id)} &middot; {_esc(fmt.get('display_name') or 'unknown format')} "
            f"&middot; generated {_stamp(timeline.get('generated_at_utc'))} by BATRIS",
            _SUB,
        ),
        HRFlowable(width="100%", thickness=0.6, color=LINE),
        Spacer(1, 10),
        Paragraph(_esc(summary.get("headline")), _HEADLINE),
        Spacer(1, 10),
        _metric_row([
            ("Health now", _num(summary.get("soh_now_percent"), 1, "%")),
            ("Condition", str(summary.get("current_state_label") or "\u2014")),
            ("Reuse grade", str(summary.get("reuse_grade") or "\u2014")),
            ("Risk band", str(summary.get("risk_band") or "\u2014")),
        ]),
        Spacer(1, 6),
        _metric_row([
            ("Cycles observed", str(summary.get("cycles_observed") or "\u2014")),
            ("SOH points lost", _num(summary.get("soh_points_lost"), 1)),
            ("Fade / 100 cycles", _num(summary.get("fade_rate_soh_points_per_100_cycles"), 2)),
            ("Events recorded", str(summary.get("n_events") or 0)),
        ]),
    ]

    chart = _soh_chart(timeline)
    if chart is not None:
        story += [
            Paragraph("Estimated health against cycle number", _H2),
            chart,
            Paragraph(
                "Bands show the healthy, second-life and below-floor regions. Dots mark "
                "cycles carrying a warning or critical event. "
                + _esc((timeline.get("series") or {}).get("method") or ""),
                _NOTE,
            ),
        ]

    phases = _phase_table(timeline)
    if phases is not None:
        story += [Paragraph("Health phases", _H2), phases]

    story += [
        Paragraph("Event log", _H2),
        Paragraph(
            "Ordered oldest first. Forward-looking entries carry no cycle number and "
            "appear last.",
            _NOTE,
        ),
        Spacer(1, 5),
        _event_table(timeline),
    ]

    projection = summary.get("projection")
    if projection:
        story += [
            Paragraph("Projection", _H2),
            _kv_table([
                ("Next threshold", f"{projection.get('target_label')} "
                                   f"({_num(projection.get('target_soh_percent'), 0, '%')})"),
                ("Cycles remaining", f"about {projection.get('cycles_remaining')} "
                                     f"from cycle {projection.get('reference_cycle')}"),
                ("At fade rate", _num(projection.get("fade_points_per_100_cycles"), 2,
                                      " SOH points per 100 cycles")),
                ("Basis", "Straight-line extrapolation of the recent trend. Fade usually "
                          "accelerates near end of life, so treat this as an upper bound "
                          "on remaining service rather than a prediction."),
            ]),
        ]

    story += [
        Paragraph("How this timeline was produced", _H2),
        Paragraph(_esc(timeline.get("method_note")), _BODY),
        Spacer(1, 4),
        Paragraph(
            "Health figures in this document are model estimates derived from operating "
            "telemetry, not measured capacity tests, and carry the confidence interval "
            "recorded in the underlying assessment. "
            + (
                "This battery was assessed from a single observation, so no dated history "
                "could be reconstructed. "
                if snapshot else ""
            )
            + "Binding reuse, warranty or disposal decisions require accredited testing.",
            _SMALL,
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
