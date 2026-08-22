"""
Command-line interface for battery assessment and passport operations.

    python -m backend.batris.cli assess B0005 --cycle 120
    python -m backend.batris.cli passport B0005 --out generated/passports/B0005.json
    python -m backend.batris.cli verify generated/passports/B0005.json --key generated/keys/issuer_public.pem
    python -m backend.batris.cli formats
    python -m backend.batris.cli tiers
    python -m backend.batris.cli assess-new examples/charge_cycle_degraded.csv \
                                     --format NASA_18650_LCO_2AH

Used for running assessments, creating and verifying passports, and checking
available battery formats and input tiers without needing the web interface.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from .assess import BatteryAssessor
from .formats import list_formats
from .paths import CYCLES_PATH, KEYS_DIR, MODELS_DIR, PASSPORTS_DIR, REPORTS_DIR

from .passport import (
    generate_keypair,
    load_passport,
    load_private_key,
    load_public_key,
    save_passport,
    verify_passport,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def _load_history(data_path: Path, battery_id: str) -> pd.DataFrame:
    if not data_path.exists():
        raise SystemExit(
            f"Feature table {data_path} not found.\n"
            "Run:  python -m backend.batris.build_dataset"
        )
    df = pd.read_csv(data_path, parse_dates=["timestamp"])
    history = df[df["battery_id"] == battery_id]
    if history.empty:
        available = ", ".join(sorted(df["battery_id"].unique()))
        raise SystemExit(
            f"Unknown battery {battery_id!r}. Available: {available}")
    return history


def cmd_assess(args) -> int:
    history = _load_history(args.data, args.battery_id)
    assessor = BatteryAssessor(args.models, variant=args.variant)
    result = assessor.assess(history, cycle_index=args.cycle,
                             include_trajectory=args.full)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    health = result["health"]
    safety = result["safety"]
    second_life = result["second_life"]
    lo, hi = health["confidence_interval_90"]

    print(f"\n  Battery {result['battery_id']}  "
          f"({result['format']['display_name']})")
    print(
        f"  Cycle {result['cycle_index']} of {result['total_cycles_observed']}")
    print("  " + "-" * 66)
    print(f"  ESTIMATED SOH        {health['soh_percent']:.2f}%   "
          f"[90% interval {100 * lo:.1f}-{100 * hi:.1f}%]")
    print(f"  Status               {health['state_of_health_label']}")
    print(f"  Remaining capacity   {health['remaining_capacity_ah']} Ah")
    if health.get("fade_rate_soh_points_per_100_cycles") is not None:
        print(f"  Fade rate            "
              f"{health['fade_rate_soh_points_per_100_cycles']:.2f} SOH pts / 100 cycles")

    reference = result.get("reference_measurement")
    if reference:
        print(f"  Reference (measured) {100 * reference['measured_soh']:.2f}%   "
              f"error {reference['estimation_error_percentage_points']:+.2f} pts   "
              f"inside interval: {reference['within_confidence_interval']}")

    print("  " + "-" * 66)
    print(
        f"  SAFETY RISK          {safety['risk_score']:.0f}/100  ({safety['risk_band']})")
    print(f"                       {safety['band_meaning']}")
    for driver in safety["risk_drivers"][:3]:
        print(f"    - {driver['finding']}")

    anomaly = result["anomaly"]
    print(f"  ANOMALIES            {anomaly['n_anomalies']} on this cycle "
          f"(max severity: {anomaly['max_severity']})")
    for item in anomaly["anomalies"][:3]:
        print(f"    - [{item['severity']}] {item['code']}")

    print("  " + "-" * 66)
    print(f"  SECOND-LIFE GRADE    {second_life['grade']}  "
          f"({second_life['grade_confidence']} confidence)")
    print(f"                       {second_life['recommendation']}")
    if second_life["grade_is_ambiguous"]:
        print(f"                       Interval spans grades "
              f"{second_life['worst_case_grade']}-{second_life['best_case_grade']}")
    print(f"  Next step            {second_life['next_step']}")

    print("  " + "-" * 66)
    print("  DEGRADATION DRIVERS")
    for factor in result["degradation_factors"][:4]:
        print(
            f"    {factor['impact_soh_percentage_points']:+7.2f} pts  {factor['label']}")
    print(f"\n  {result['degradation_summary']}")

    print("  " + "-" * 66)
    print("  SAFE CHARGING ENVELOPE")
    envelope = safety["safe_charging_envelope"]
    print(f"    Max current   {envelope['max_charge_current_a']} A "
          f"({envelope['max_charge_c_rate']}C, "
          f"{100 * envelope['derating_applied']:.0f}% derated)")
    print(f"    SOC window    {envelope['recommended_soc_window_percent'][0]}-"
          f"{envelope['recommended_soc_window_percent'][1]}%")
    if envelope.get("charge_voltage_setpoint_v"):
        print(f"    CV setpoint   {envelope['charge_voltage_setpoint_v']} V "
              f"(upper bound only; enforce the lower bound from BMS SOC)")
    print(f"    Charge temp   {envelope['charge_temperature_window_c'][0]}-"
          f"{envelope['charge_temperature_window_c'][1]} C")

    print("  " + "-" * 66)
    print("  NOTE: every figure above is an ESTIMATE from operating telemetry,")
    print("        not a certified capacity measurement.\n")
    return 0


def cmd_passport(args) -> int:
    history = _load_history(args.data, args.battery_id)
    keys = generate_keypair(args.keys)
    private_key = load_private_key(keys["private"])

    assessor = BatteryAssessor(args.models, variant=args.variant)
    document = assessor.issue_passport(
        history, private_key, cycle_index=args.cycle,
        include_certified_test=args.include_reference,
    )

    out_path = args.out or PASSPORTS_DIR / f"{args.battery_id}_passport.json"
    save_passport(document, out_path)

    payload = document["payload"]
    print(f"\n  Passport issued: {out_path}")
    print(f"  Passport ID      {payload['passport_id']}")
    print(f"  Battery          {payload['battery']['battery_id']}")
    print(f"  Health method    {payload['health_estimate']['method']}")
    print(
        f"  SOH              {payload['health_estimate']['soh_percent']:.2f}%")
    print(f"  Grade            {payload['second_life_assessment']['grade']}")
    print(f"  Certified test   {payload['certified_test']['method']}")
    print(
        f"  Signature        Ed25519, key {document['signature']['public_key_fingerprint']}")
    print(f"\n  Verify with:")
    print(
        f"    python -m backend.batris.cli verify {out_path} --key {keys['public']}\n")
    return 0


def cmd_verify(args) -> int:
    document = load_passport(args.passport)
    public_key = load_public_key(args.key) if args.key else None
    result = verify_passport(document, public_key)

    print()
    if result["valid"]:
        print("  SIGNATURE VALID")
        print(f"    Trust anchor     {result['trust_anchor']}")
        print(f"    Key fingerprint  {result['public_key_fingerprint']}")
        print(f"    Passport ID      {result['passport_id']}")
        print(f"    Battery          {result['battery_id']}")
        print(f"    Issued           {result['issued_at_utc']}")
        print(f"    Health method    {result['health_method']}")
        print(f"    Certified test   {result['certified_test_status']}")
    else:
        print("  SIGNATURE INVALID")
        for error in result["errors"]:
            print(f"    - {error}")

    for warning in result.get("warnings", []):
        print(f"\n  WARNING: {warning}")
    print()
    return 0 if result["valid"] else 1


def _print_unseen(result) -> None:
    """Shared console rendering for an unseen-battery assessment."""
    health = result["health"]
    tier = result["input_tier"]
    accuracy = tier.get("measured_accuracy", {})
    lo, hi = health["confidence_interval_90"]

    print(
        f"\n  Battery {result['battery_id']}  ({result['format']['display_name']})")
    print("  " + "-" * 66)
    print(
        f"  INPUT LEVEL          Tier {tier['rank']} - {tier['display_name']}")
    print(f"                       {tier['n_features']} signals used")
    if accuracy:
        print(f"  MEASURED ACCURACY    {accuracy.get('mae_soh_percentage_points')} "
              f"SOH points mean error (R2 {accuracy.get('r2')})")
        print(f"                       worst cell in validation: "
              f"{accuracy.get('worst_battery_mae_soh_points')} SOH points")

    if result["assumptions"]:
        print("  ASSUMPTIONS MADE")
        for item in result["assumptions"]:
            print(f"    - {item}")

    transfer = result["chemistry_transfer"]
    if not transfer["in_distribution"]:
        print("  " + "-" * 66)
        print(f"  !! EXTRAPOLATION: {transfer['requested_chemistry']} is outside "
              f"the training data ({', '.join(transfer['trained_chemistries'])}).")
        print(f"     Interval widened {transfer['interval_factor']}x. "
              "This factor is a judgement, not a measured quantity.")

    print("  " + "-" * 66)
    print(f"  ESTIMATED SOH        {health['soh_percent']:.2f}%   "
          f"[90% interval {100 * lo:.1f}-{100 * hi:.1f}%]")
    print(f"  Status               {health['state_of_health_label']}")
    print(f"  Remaining capacity   {health['remaining_capacity_ah']} Ah")

    safety = result["safety"]
    print(
        f"  SAFETY RISK          {safety['risk_score']:.0f}/100  ({safety['risk_band']})")
    for driver in safety["risk_drivers"][:3]:
        print(f"    - {driver['finding']}")

    anomaly = result["anomaly"]
    ran = sum(1 for v in anomaly.get("detectors_run", {}).values() if v)
    print(f"  ANOMALIES            {anomaly['n_anomalies']} "
          f"({ran} of 3 detectors could run)")
    for item in anomaly["anomalies"][:3]:
        print(f"    - [{item['severity']}] {item['code']}")

    second_life = result["second_life"]
    print("  " + "-" * 66)
    print(f"  SECOND-LIFE GRADE    {second_life['grade']}  "
          f"({second_life['grade_confidence']} confidence)")
    print(f"                       {second_life['recommendation']}")
    print(f"  Next step            {second_life['next_step']}")

    print("  " + "-" * 66)
    print("  DEGRADATION DRIVERS")
    for factor in result["degradation_factors"][:4]:
        print(
            f"    {factor['impact_soh_percentage_points']:+7.2f} pts  {factor['label']}")

    print("  " + "-" * 66)
    print("  COULD NOT BE ASSESSED")
    for item in result["unavailable_analyses"]:
        print(f"    - {item['analysis']}: {item['reason']}")

    print("  " + "-" * 66)
    print("  NOTE: this is an ESTIMATE from the information supplied, not a")
    print("        certified capacity measurement.\n")


def cmd_assess_new(args) -> int:
    """Assess a battery from an uploaded charge log."""
    from .assess_unseen import UnseenBatteryAssessor
    from .onboard import OnboardingError, from_telemetry_csv

    if not args.csv.exists():
        raise SystemExit(f"File not found: {args.csv}")

    try:
        row, tier, assumptions = from_telemetry_csv(
            args.csv.read_text(encoding="utf-8"),
            format_key=args.format_key,
            battery_id=args.battery_id,
            ambient_temp_c=args.ambient,
            re_ohm=args.re_ohm,
            rct_ohm=args.rct_ohm,
        )
    except OnboardingError as exc:
        raise SystemExit(f"\n  Could not use this file:\n    {exc}\n")

    result = UnseenBatteryAssessor(args.models).assess(row, tier, assumptions)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    _print_unseen(result)
    return 0


def cmd_tiers(args) -> int:
    """Show what information each input tier needs and what it delivers."""
    from .tiers import TIER_ORDER, get_tier

    report_path = REPORTS_DIR / "tier_training_report.json"
    measured = {}
    if report_path.exists():
        measured = json.loads(report_path.read_text()).get("tiers", {})

    print("\n  Input tiers for assessing a battery with no recorded history\n")
    for key in TIER_ORDER:
        tier = get_tier(key)
        stats = measured.get(key, {}).get("validation", {})
        print(f"  TIER {tier.rank}: {tier.display_name}")
        print(f"    source     {tier.source}")
        print(f"    signals    {len(tier.features)}")
        if stats:
            print(f"    accuracy   {stats.get('mae_soh_points')} SOH points "
                  f"mean error, R2 {stats.get('r2')} "
                  f"(leave-one-battery-out)")
            print(
                f"    worst cell {stats.get('worst_battery_mae_soh_points')} SOH points")
        if not tier.reliable:
            print("    NOTE       indicative only; no reuse grade is issued")
        print(f"    {tier.description}")
        print()
    return 0


def cmd_formats(args) -> int:
    print("\n  Registered battery formats\n")
    for key, fmt in list_formats().items():
        print(f"  {key}")
        print(f"    {fmt.display_name}")
        print(f"    {fmt.chemistry} {fmt.form_factor}  |  "
              f"{fmt.rated_capacity_ah} Ah  |  "
              f"{fmt.v_min}-{fmt.v_max} V  |  "
              f"EOL at {100 * fmt.eol_soh:.0f}% SOH")
        print()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="batris",
        description="Battery Health & Second-Life Passport Platform CLI",
    )
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--models", type=Path, default=MODELS_DIR)
    parser.add_argument("--keys", type=Path, default=KEYS_DIR)

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("assess", help="Assess a battery's health and safety")
    p.add_argument("battery_id")
    p.add_argument("--cycle", type=int,
                   help="Cycle to assess (default: latest)")
    p.add_argument("--variant", default="full",
                   choices=["full", "provenance_free"])
    p.add_argument("--json", action="store_true", help="Emit raw JSON")
    p.add_argument("--full", action="store_true",
                   help="Include the trajectory series")
    p.set_defaults(func=cmd_assess)

    p = sub.add_parser("passport", help="Issue a signed second-life passport")
    p.add_argument("battery_id")
    p.add_argument("--cycle", type=int)
    p.add_argument("--variant", default="full",
                   choices=["full", "provenance_free"])
    p.add_argument("--out", type=Path)
    p.add_argument("--include-reference", action="store_true",
                   help="Include the dataset's reference discharge measurement")
    p.set_defaults(func=cmd_passport)

    p = sub.add_parser("verify", help="Verify a passport signature")
    p.add_argument("passport", type=Path)
    p.add_argument("--key", type=Path,
                   help="Issuer public key (omit to use the embedded key, which "
                        "checks integrity but not authorship)")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("formats", help="List registered battery formats")
    p.set_defaults(func=cmd_formats)

    p = sub.add_parser(
        "assess-new",
        help="Assess a battery not in the dataset, from a charge log CSV",
    )
    p.add_argument("csv", type=Path, help="CSV with time_s, voltage_v, current_a, "
                                          "temperature_c for one charge cycle")
    p.add_argument("--format", dest="format_key", required=True,
                   help="Battery format key (see: batris formats)")
    p.add_argument("--battery-id", default="USER-BATTERY")
    p.add_argument("--ambient", type=float, help="Ambient temperature in degC")
    p.add_argument("--re-ohm", type=float, help="EIS electrolyte resistance")
    p.add_argument("--rct-ohm", type=float,
                   help="EIS charge-transfer resistance")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_assess_new)

    p = sub.add_parser(
        "tiers", help="Show input tiers and their measured accuracy")
    p.set_defaults(func=cmd_tiers)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
