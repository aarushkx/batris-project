"""
Second-life marketplace listings.

A listing is *derived* from an assessment, never typed in. The seller supplies
only context a model cannot know — where the pack is, what it came out of, how
to reach them — while every health, safety and grade figure on the card is
copied from the assessment document the platform itself produced. That is the
whole point: a buyer browsing this inventory is reading the same numbers the
dashboard produced and the same numbers a signed passport would carry, so a
seller cannot inflate a grade by editing a form field.

No pricing, escrow or payment lives here by design. The platform's claim is
about *condition*, not about value. Buyers get the seller's contact details and
negotiate off-platform, which keeps the trust boundary exactly where the
cryptographic passport can support it.

Storage reuses the same MongoDB connection as the auth store rather than
opening a second client.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .auth import get_auth_store

try:
    from pymongo import ASCENDING, DESCENDING
except ImportError:  # pragma: no cover - dependency present in deployment
    ASCENDING = 1
    DESCENDING = -1

# Reuse grades a listing can carry, in the order the market page shows them.
GRADE_ORDER = ["A", "B", "C", "RECYCLE"]

MAX_TITLE = 90
MAX_LOCATION = 80
MAX_NOTES = 600


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _finite(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _clean_text(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    # Collapse whitespace so a pasted block cannot break card layout.
    text = " ".join(text.split())
    return text[:limit]


def derive_listing_facts(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Pull every published figure for a listing out of an assessment.

    Raises ValueError when the document is not a usable assessment, so a
    malformed or hand-written payload can never become a listing.
    """
    if not isinstance(assessment, dict) or not assessment:
        raise ValueError("An assessment document is required to publish a listing.")

    health = assessment.get("health") or {}
    second_life = assessment.get("second_life") or {}
    safety = assessment.get("safety") or {}
    anomaly = assessment.get("anomaly") or {}
    fmt = assessment.get("format") or {}

    soh = _finite(health.get("soh"))
    if soh is None:
        raise ValueError("Assessment has no state-of-health estimate.")

    grade = str(second_life.get("grade") or "").upper()
    if grade not in GRADE_ORDER:
        raise ValueError(
            "Assessment carries no reuse grade, so it cannot be listed. "
            "Grades are only issued when the input tier supports one."
        )

    interval = health.get("confidence_interval_90") or []
    lower = _finite(interval[0]) if len(interval) == 2 else None
    upper = _finite(interval[1]) if len(interval) == 2 else None

    rated_ah = _finite(fmt.get("rated_capacity_ah"))
    nominal_v = _finite(fmt.get("nominal_voltage_v"))

    return {
        "battery_id": str(assessment.get("battery_id") or "Battery"),
        # -- format ------------------------------------------------------
        "format_key": fmt.get("key"),
        "format_display_name": fmt.get("display_name"),
        "chemistry": (fmt.get("chemistry") or "OTHER").upper(),
        "form_factor": fmt.get("form_factor"),
        "rated_capacity_ah": rated_ah,
        "nominal_voltage_v": nominal_v,
        # -- health ------------------------------------------------------
        "soh": round(soh, 4),
        "soh_percent": round(100 * soh, 1),
        "soh_lower_percent": None if lower is None else round(100 * lower, 1),
        "soh_upper_percent": None if upper is None else round(100 * upper, 1),
        "health_label": health.get("state_of_health_label"),
        "retained_capacity_ah": _finite(health.get("remaining_capacity_ah")),
        "remaining_energy_wh": _finite(second_life.get("estimated_remaining_energy_wh")),
        "fade_rate_soh_points_per_100_cycles": _finite(
            health.get("fade_rate_soh_points_per_100_cycles")
        ),
        # -- grade -------------------------------------------------------
        "grade": grade,
        "grade_recommendation": second_life.get("recommendation"),
        "grade_rationale": second_life.get("rationale"),
        "grade_confidence": second_life.get("grade_confidence"),
        "grade_is_ambiguous": bool(second_life.get("grade_is_ambiguous")),
        "worst_case_grade": second_life.get("worst_case_grade"),
        "best_case_grade": second_life.get("best_case_grade"),
        "next_step": second_life.get("next_step"),
        "safety_override_applied": bool(second_life.get("safety_override_applied")),
        # -- safety and anomalies ----------------------------------------
        "risk_band": safety.get("risk_band"),
        "risk_score": _finite(safety.get("risk_score")),
        "anomaly_max_severity": anomaly.get("max_severity"),
        "anomaly_count": int(anomaly.get("n_anomalies") or 0),
        # -- provenance ---------------------------------------------------
        "assessed_at_cycle": assessment.get("cycle_index"),
        "cycles_observed": assessment.get("total_cycles_observed"),
        "assessed_at": assessment.get("timestamp"),
        "has_trajectory": bool((assessment.get("trajectory") or {}).get("cycle_index")),
        "is_unseen_battery": bool(assessment.get("is_unseen_battery")),
    }


class MarketStore:
    """Listing CRUD over the shared MongoDB database."""

    def __init__(self) -> None:
        self.listings = get_auth_store().db["market_listings"]
        self.listings.create_index([("listing_id", ASCENDING)], unique=True)
        self.listings.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
        self.listings.create_index([("seller_id", ASCENDING), ("created_at", DESCENDING)])

    # ------------------------------------------------------------ create
    def create(
        self,
        user: Dict[str, Any],
        assessment: Dict[str, Any],
        title: Any = None,
        location: Any = None,
        notes: Any = None,
        passport: Optional[Dict[str, Any]] = None,
        is_reference_fleet: bool = False,
        listing_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        facts = derive_listing_facts(assessment)

        passport_id = None
        if isinstance(passport, dict):
            passport_id = (passport.get("payload") or {}).get("passport_id")

        document = {
            "listing_id": listing_id or str(uuid.uuid4()),
            "status": "active",
            # The seller's public profile. Publishing is an explicit, revocable
            # act, and the form says plainly that these two fields become
            # visible to everyone.
            "seller_id": str(user["id"]),
            "seller_name": user.get("name") or "Seller",
            "seller_email": user.get("email") or "",
            "title": _clean_text(title, MAX_TITLE) or None,
            "location": _clean_text(location, MAX_LOCATION) or None,
            "notes": _clean_text(notes, MAX_NOTES) or None,
            "is_reference_fleet": bool(is_reference_fleet),
            "passport_id": passport_id,
            "assessment": assessment,
            "passport": passport if isinstance(passport, dict) else None,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            **facts,
        }

        self.listings.update_one(
            {"listing_id": document["listing_id"]},
            {"$set": document},
            upsert=True,
        )
        return self.public(document)

    # -------------------------------------------------------------- read
    @staticmethod
    def public(document: Dict[str, Any], include_assessment: bool = False) -> Dict[str, Any]:
        """Shape a stored listing for the API.

        Drops the Mongo id and the seller's internal id; keeps name and email,
        which the seller consented to publish when creating the listing.
        """
        out = {
            key: value
            for key, value in document.items()
            if key not in {"_id", "seller_id", "assessment", "passport"}
        }
        out["seller"] = {
            "name": document.get("seller_name") or "Seller",
            "email": document.get("seller_email") or "",
        }
        out.pop("seller_name", None)
        out.pop("seller_email", None)
        if include_assessment:
            out["assessment"] = document.get("assessment")
            out["passport"] = document.get("passport")
        return out

    def get(self, listing_id: str, include_assessment: bool = True) -> Dict[str, Any]:
        document = self.listings.find_one({"listing_id": str(listing_id)})
        if not document or document.get("status") != "active":
            raise HTTPException(status_code=404, detail="That listing is no longer available.")
        return self.public(document, include_assessment=include_assessment)

    def browse(
        self,
        grade: Optional[str] = None,
        chemistry: Optional[str] = None,
        min_soh_percent: Optional[float] = None,
        limit: int = 120,
    ) -> Dict[str, Any]:
        """Filtered inventory plus grade counts over the whole active set.

        Counts are deliberately computed before filtering: the tiles at the top
        of the market page describe the inventory, and would be useless if they
        only ever agreed with whatever filter happened to be applied.
        """
        active = list(
            self.listings.find({"status": "active"}).sort("created_at", DESCENDING).limit(500)
        )

        counts = {key: 0 for key in GRADE_ORDER}
        chemistries: Dict[str, int] = {}
        for document in active:
            listing_grade = str(document.get("grade") or "").upper()
            if listing_grade in counts:
                counts[listing_grade] += 1
            key = str(document.get("chemistry") or "OTHER").upper()
            chemistries[key] = chemistries.get(key, 0) + 1

        selected = active
        if grade and str(grade).upper() in GRADE_ORDER:
            wanted = str(grade).upper()
            selected = [d for d in selected if str(d.get("grade") or "").upper() == wanted]
        if chemistry:
            wanted = str(chemistry).upper()
            selected = [
                d for d in selected if str(d.get("chemistry") or "").upper() == wanted
            ]
        threshold = _finite(min_soh_percent)
        if threshold is not None:
            selected = [
                d for d in selected
                if (_finite(d.get("soh_percent")) or 0.0) >= threshold
            ]

        return {
            "items": [self.public(d) for d in selected[:limit]],
            "counts": counts,
            "total": len(active),
            "filtered": len(selected),
            "chemistries": sorted(chemistries.keys()),
        }

    def for_seller(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = (
            self.listings.find({"seller_id": str(user_id)})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return [self.public(document) for document in rows]

    # ------------------------------------------------------------ delete
    def withdraw(self, listing_id: str, user_id: str) -> Dict[str, Any]:
        document = self.listings.find_one({"listing_id": str(listing_id)})
        if not document:
            raise HTTPException(status_code=404, detail="Listing not found.")
        if str(document.get("seller_id")) != str(user_id):
            raise HTTPException(
                status_code=403, detail="You can only withdraw your own listings."
            )
        self.listings.update_one(
            {"listing_id": str(listing_id)},
            {"$set": {"status": "withdrawn", "updated_at": _utc_now()}},
        )
        return {"withdrawn": True, "listing_id": str(listing_id)}


_store: Optional[MarketStore] = None


def get_market_store() -> MarketStore:
    global _store
    if _store is None:
        try:
            _store = MarketStore()
        except HTTPException:
            raise
        except Exception as exc:  # surface connection/config problems cleanly
            raise HTTPException(
                status_code=503,
                detail=f"The second-life market is unavailable: {exc}",
            ) from exc
    return _store
