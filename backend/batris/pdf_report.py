"""Renders a signed battery passport as a printable PDF.

This only handles the PDF layout. It does not change or re-sign the passport.
It uses the signed document data and clearly shows estimated and certified
values.
"""

from __future__ import annotations

from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from io import BytesIO

_STYLES = getSampleStyleSheet()

_TITLE = ParagraphStyle(
    "PassportTitle", parent=_STYLES["Heading1"], fontSize=18, spaceAfter=2,
)
_SUB = ParagraphStyle(
    "PassportSub", parent=_STYLES["Normal"], textColor=colors.HexColor("#5b6472"),
    fontSize=9, spaceAfter=10,
)
_H2 = ParagraphStyle(
    "PassportH2", parent=_STYLES["Heading2"], fontSize=11.5, spaceBefore=14,
    spaceAfter=6, textColor=colors.HexColor("#1c2230"),
)
_BODY = ParagraphStyle(
    "PassportBody", parent=_STYLES["Normal"], fontSize=9.3, leading=13)
_MONO = ParagraphStyle(
    "PassportMono", parent=_STYLES["Normal"], fontName="Courier", fontSize=7.6,
    leading=10, textColor=colors.HexColor("#454c58"),
)
_DISCLAIMER = ParagraphStyle(
    "PassportDisclaimer", parent=_STYLES["Normal"], fontSize=8.3, leading=12,
    textColor=colors.HexColor("#7a1f1f"), borderPadding=6,
)


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", _BODY),
             Paragraph(str(v), _BODY)] for k, v in rows]
    table = Table(data, colWidths=[48 * mm, 112 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e4e7ec")),
            ]
        )
    )
    return table


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "\u2014"
    if isinstance(value, float):
        return f"{value:.3f}{suffix}"
    return f"{value}{suffix}"


def _fmt_ci(interval) -> str:
    """`confidence_interval_90` is stored as a [lower, upper] fraction (0-1)."""
    if not interval or len(interval) != 2:
        return "\u2014"
    lower, upper = interval
    try:
        return f"{float(lower) * 100:.1f}\u2013{float(upper) * 100:.1f} %"
    except (TypeError, ValueError):
        return "\u2014"


def render_passport_pdf(document: Dict) -> bytes:
    """Renders a signed passport document to PDF bytes."""
    payload = document.get("payload", {}) or {}
    signature = document.get("signature", {}) or {}

    battery = payload.get("battery", {}) or {}
    health = payload.get("health_estimate", {}) or {}
    second_life = payload.get("second_life_assessment", {}) or {}
    safety = payload.get("safety_assessment", {}) or {}
    certified = payload.get("certified_test", {}) or {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Battery Passport {payload.get('passport_id', '')}",
    )

    story = [
        Paragraph("Second-life battery passport", _TITLE),
        Paragraph(
            f"Passport ID {payload.get('passport_id', '\u2014')} &middot; "
            f"issued {payload.get('issued_at_utc', '\u2014')} by "
            f"{payload.get('issuer', '\u2014')}",
            _SUB,
        ),
        HRFlowable(width="100%", thickness=0.6,
                   color=colors.HexColor("#d7dbe2")),
        Paragraph("Battery", _H2),
        _kv_table(
            [
                ("Battery ID", battery.get("battery_id", "\u2014")),
                ("Format", (battery.get("format") or {}).get(
                    "display_name", "\u2014")),
            ]
        ),
        Paragraph("Health estimate (ESTIMATED, not a certified measurement)", _H2),
        _kv_table(
            [
                ("State of health", _fmt(health.get("soh_percent"), " %")),
                ("Confidence interval", _fmt_ci(
                    health.get("confidence_interval_90"))),
                ("Method", health.get("method", "\u2014")),
            ]
        ),
        Paragraph("Second-life assessment", _H2),
        _kv_table(
            [
                ("Reuse grade", second_life.get("grade", "\u2014")),
                ("Recommended next step", second_life.get("next_step", "\u2014")),
            ]
        ),
        Paragraph("Safety", _H2),
        _kv_table(
            [
                ("Risk band", safety.get("risk_band", "\u2014")),
                ("What this means", safety.get("band_meaning", "\u2014")),
            ]
        ),
        Paragraph("Certified test", _H2),
        Paragraph(certified.get("method_description",
                  certified.get("method", "\u2014")), _BODY),
        # Spacer(1, 10),
        # Paragraph("Disclaimer", _H2),
        # Paragraph(payload.get("disclaimer", ""), _DISCLAIMER),
        # Spacer(1, 12),
        Paragraph("Digital signature", _H2),
        _kv_table(
            [
                ("Algorithm", signature.get("algorithm", "\u2014")),
                ("Signed at", signature.get("signed_at_utc", "\u2014")),
                ("Key fingerprint", signature.get(
                    "public_key_fingerprint", "\u2014")),
            ]
        ),
        Paragraph(
            "Signature value (hex) &mdash; verify this document against the "
            "issuer's published public key rather than trusting this PDF alone:",
            _BODY,
        ),
        Spacer(1, 4),
        Paragraph(signature.get("value", ""), _MONO),
    ]

    doc.build(story)
    return buffer.getvalue()
