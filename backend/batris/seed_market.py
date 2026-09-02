"""
Populate the second-life market with the dataset batteries.

Without this the market is empty on a fresh install, which makes the feature
impossible to demonstrate. The listings it creates are real: each one is
published from an actual assessment produced by the same pipeline the
dashboard uses, so the cards carry genuine model output rather than
hand-written numbers.

They are flagged `is_reference_fleet`, and the UI labels them as such. A
marketplace that quietly padded itself with fake inventory would undermine the
one thing this platform is trying to establish, which is that a number on a
card can be trusted.

Usage::

    python -m backend.batris.seed_market
    python -m backend.batris.seed_market --reset
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Dict, List

import pandas as pd

from .assess import BatteryAssessor, build_lobo_trajectory_cache
from .auth import get_auth_store
from .marketplace import get_market_store
from .paths import CYCLES_PATH, MODELS_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
logger = logging.getLogger("seed_market")

DEMO_SELLER = {
    "name": "BATRIS Reference Fleet",
    "email": "reference.fleet@batris.example",
}

# Plausible second-life context for each cell. Only the free-text fields a
# seller would supply are set here; every health figure comes from the model.
CONTEXT: Dict[str, Dict[str, str]] = {
    "B0005": {
        "title": "18650 LCO cell, retired from cycling rig",
        "location": "Bengaluru, KA",
        "notes": (
            "Retired from a laboratory cycling rig after 168 full charge-discharge "
            "cycles at ambient temperature. Casing intact, terminals clean, no "
            "swelling. Held in dry storage at partial charge since removal."
        ),
    },
    "B0006": {
        "title": "18650 LCO cell, matched-set spare",
        "location": "Pune, MH",
        "notes": (
            "One of a matched set of four cells cycled under identical conditions. "
            "Suitable for anyone who wants cells with a documented, comparable "
            "history rather than mixed-provenance stock."
        ),
    },
    "B0007": {
        "title": "18650 LCO cell, highest retained capacity in batch",
        "location": "Bengaluru, KA",
        "notes": (
            "The strongest cell of the batch on retained capacity. Charge profile "
            "still shows a long constant-current phase, which is consistent with "
            "the lower lithium inventory loss the assessment reports."
        ),
    },
    "B0018": {
        "title": "18650 LCO cell, shorter service history",
        "location": "Hyderabad, TS",
        "notes": (
            "Withdrawn earlier than the rest of the batch at 132 cycles. Fewer "
            "cycles on record, but read the confidence interval before assuming "
            "that means more life left."
        ),
    },
}


def _ensure_demo_seller() -> Dict[str, str]:
    """Find or create the reference-fleet account that owns seed listings."""
    store = get_auth_store()
    existing = store.users.find_one({"email": DEMO_SELLER["email"]})
    if existing:
        return store._public_user(existing)  # noqa: SLF001 - same package

    # A long random password: this account exists to own listings, and is not
    # meant to be signed into.
    import secrets

    user = store.create_user(
        DEMO_SELLER["name"], DEMO_SELLER["email"], secrets.token_urlsafe(24)
    )
    logger.info("Created reference-fleet seller account %s", DEMO_SELLER["email"])
    return user


def seed(reset: bool = False) -> List[str]:
    if not CYCLES_PATH.exists():
        raise SystemExit(
            f"Feature table {CYCLES_PATH} not found. Run:\n"
            "  python -m backend.batris.build_dataset"
        )

    market = get_market_store()
    seller = _ensure_demo_seller()

    if reset:
        removed = market.listings.delete_many({"is_reference_fleet": True})
        logger.info("Removed %d existing reference listings", removed.deleted_count)

    cycles = pd.read_csv(CYCLES_PATH, parse_dates=["timestamp"])
    cycles = cycles.sort_values(["battery_id", "cycle_index"]).reset_index(drop=True)

    logger.info("Building leave-one-battery-out trajectories...")
    assessor = BatteryAssessor(
        MODELS_DIR, variant="full",
        lobo_trajectories=build_lobo_trajectory_cache(cycles),
    )

    published: List[str] = []
    for battery_id in sorted(cycles["battery_id"].unique()):
        history = cycles[cycles["battery_id"] == battery_id]
        assessment = assessor.assess(history)
        context = CONTEXT.get(str(battery_id), {})

        # A stable listing id keeps re-seeding idempotent instead of producing
        # a duplicate card every time this runs.
        listing = market.create(
            seller,
            assessment,
            title=context.get("title"),
            location=context.get("location"),
            notes=context.get("notes"),
            is_reference_fleet=True,
            listing_id=f"reference-fleet-{battery_id}",
        )
        published.append(listing["listing_id"])
        logger.info(
            "Listed %s — %.1f%% SOH, grade %s, risk %s",
            battery_id,
            listing["soh_percent"],
            listing["grade"],
            listing["risk_band"],
        )

    counts = market.browse()["counts"]
    logger.info("Market now holds %d active listings %s", len(published), counts)
    return published


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing reference-fleet listings before seeding.",
    )
    args = parser.parse_args(argv)
    try:
        seed(reset=args.reset)
    except Exception as exc:  # noqa: BLE001 - a CLI should explain itself
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
