"""FastAPI web server for the BATRIS - Battery Traceability & Reliability Intelligence System"""

from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .assess import BatteryAssessor
from .assess_unseen import TRAINED_CHEMISTRIES, UnseenBatteryAssessor
from .formats import list_formats, register_custom_format
from .onboard import (
    TELEMETRY_COLUMNS,
    OnboardingError,
    from_questionnaire,
    from_telemetry_csv,
)
from .models.soh import SOHModel
from .passport import (
    generate_keypair,
    load_private_key,
    load_public_key,
    verify_passport,
)
from .pdf_report import render_passport_pdf
from .paths import CYCLES_PATH, KEYS_DIR, MODELS_DIR, PASSPORTS_DIR, PROJECT_ROOT
from .tiers import TIER_ORDER, questionnaire_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api")

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _json_safe(value):
    """Convert numpy scalars and NaN into JSON-representable values."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def create_app(
    data_path: Path | str = CYCLES_PATH,
    models_dir: Path | str = MODELS_DIR,
    keys_dir: Path | str = KEYS_DIR,
) -> FastAPI:
    app = FastAPI(
        title="BATRIS - Battery Traceability & Reliability Intelligence System",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    data_path = Path(data_path)
    models_dir = Path(models_dir)
    keys_dir = Path(keys_dir)

    if not data_path.exists():
        raise FileNotFoundError(
            f"Feature table {data_path} not found. Run:\n"
            "  python -m backend.batris.build_dataset"
        )

    cycles = pd.read_csv(data_path, parse_dates=["timestamp"])
    cycles = cycles.sort_values(
        ["battery_id", "cycle_index"]).reset_index(drop=True)

    assessors: Dict[str, BatteryAssessor] = {}

    def get_assessor(variant: str) -> BatteryAssessor:
        if variant not in assessors:
            assessors[variant] = BatteryAssessor(models_dir, variant=variant)
        return assessors[variant]

    get_assessor("full")

    keys = generate_keypair(keys_dir)
    private_key = load_private_key(keys["private"])

    @app.get("/api/batteries")
    def batteries():
        out = []
        for battery_id, group in cycles.groupby("battery_id"):
            out.append({
                "battery_id": battery_id,
                "format_key": group["format_key"].iloc[0],
                "cycles": int(len(group)),
                "first_cycle": int(group["cycle_index"].min()),
                "last_cycle": int(group["cycle_index"].max()),
                "measured_soh_range": [
                    round(float(group["soh"].max()), 4),
                    round(float(group["soh"].min()), 4),
                ],
            })
        return _json_safe(out)

    @app.get("/api/formats")
    def formats():
        return _json_safe({key: fmt.as_dict() for key, fmt in list_formats().items()})

    @app.get("/api/model-info")
    def model_info():
        info = {}
        for variant in ("full", "provenance_free"):
            try:
                assessor = get_assessor(variant)
            except FileNotFoundError:
                continue
            info[variant] = {
                "features": assessor.soh_model.features,
                "metadata": assessor.soh_model.metadata,
                "interval_calibration_factor": assessor.soh_model.calibration_factor,
            }

        info["anomaly_detector"] = assessors["full"].anomaly_detector.metadata

        tiers = []
        for tier_key in TIER_ORDER:
            try:
                model = SOHModel.load(models_dir, variant=f"tier_{tier_key}")
            except FileNotFoundError:
                continue
            validation = model.metadata.get("validation", {})
            tiers.append({
                "key": tier_key,
                "rank": model.metadata.get("tier_rank"),
                "display_name": model.metadata.get("tier_display_name"),
                "reliable": model.metadata.get("tier_reliable", True),
                "n_features": len(model.features),
                "mae_soh_points": validation.get("mae_soh_percentage_points"),
                "r2": validation.get("r2"),
                "worst_battery_mae_soh_points": validation.get(
                    "worst_battery_mae_soh_points"
                ),
                "interval_calibration_factor": model.calibration_factor,
            })
        info["tiers"] = tiers
        return _json_safe(info)

    @app.get("/api/assess/{battery_id}")
    def assess(
        battery_id: str,
        cycle: Optional[int] = Query(None),
        variant: str = Query("full"),
    ):
        history = cycles[cycles["battery_id"] == battery_id]
        if history.empty:
            raise HTTPException(
                status_code=404, detail=f"Unknown battery {battery_id!r}")

        if variant not in ("full", "provenance_free"):
            raise HTTPException(
                status_code=400, detail=f"Unknown variant {variant!r}")

        try:
            result = get_assessor(variant).assess(history, cycle_index=cycle)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _json_safe(result)

    PASSPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Registered before /api/passport/{battery_id} — otherwise FastAPI would
    # match "pdf" as a battery_id and this route would never be reached.
    @app.post("/api/passport/pdf")
    def passport_pdf(document: Optional[Dict] = Body(None)):
        """Renders a signed passport document to PDF and stores it so it can
        be fetched by a stable URL — the thing a QR code actually needs to
        point at, since a camera scan can only trigger a GET request."""
        if not document:
            raise HTTPException(
                status_code=400,
                detail="Request body must be a passport JSON document",
            )

        passport_id = (
            (document.get("payload") or {}).get("passport_id") or str(uuid.uuid4())
        )
        try:
            pdf_bytes = render_passport_pdf(document)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            raise HTTPException(
                status_code=400, detail=f"Could not render PDF: {exc}"
            ) from exc

        pdf_path = PASSPORTS_DIR / f"{passport_id}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        return {"passport_id": passport_id, "pdf_url": f"/api/passport/pdf/{passport_id}"}

    @app.get("/api/passport/pdf/{passport_id}")
    def get_passport_pdf(passport_id: str):
        pdf_path = PASSPORTS_DIR / f"{passport_id}.pdf"
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail="No PDF for this passport yet. Generate it first via POST /api/passport/pdf.",
            )
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"passport_{passport_id}.pdf",
        )

    @app.post("/api/passport/{battery_id}")
    def passport(battery_id: str, body: Optional[Dict] = Body(None)):
        history = cycles[cycles["battery_id"] == battery_id]
        if history.empty:
            raise HTTPException(
                status_code=404, detail=f"Unknown battery {battery_id!r}")

        body = body or {}
        variant = body.get("variant", "full")
        cycle = body.get("cycle")
        include_reference = bool(
            body.get("include_reference_measurement", False))

        try:
            document = get_assessor(variant).issue_passport(
                history,
                private_key,
                cycle_index=cycle,
                include_certified_test=include_reference,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _json_safe(document)

    @app.post("/api/verify")
    def verify(
        document: Optional[Dict] = Body(None),
        use_issuer_key: bool = Query(False),
    ):
        if not document:
            raise HTTPException(
                status_code=400,
                detail="Request body must be a passport JSON document",
            )

        public_key = load_public_key(
            keys["public"]) if use_issuer_key else None
        return _json_safe(verify_passport(document, public_key))

    @app.get("/api/issuer-public-key")
    def issuer_public_key():
        return {
            "public_key_pem": Path(keys["public"]).read_text(),
            "note": (
                "In production this key would be published through an independent "
                "registry, not served by the same host that issues the passports."
            ),
        }

    unseen_assessor: Dict[str, UnseenBatteryAssessor] = {}

    def get_unseen() -> UnseenBatteryAssessor:
        if "instance" not in unseen_assessor:
            unseen_assessor["instance"] = UnseenBatteryAssessor(models_dir)
        return unseen_assessor["instance"]

    @app.get("/api/onboarding/schema")
    def onboarding_schema():
        schema = questionnaire_schema()
        schema["formats"] = [
            {
                "key": key,
                "display_name": fmt.display_name,
                "chemistry": fmt.chemistry,
                "rated_capacity_ah": fmt.rated_capacity_ah,
                "nominal_voltage_v": fmt.nominal_voltage_v,
                "in_training_distribution": fmt.chemistry in TRAINED_CHEMISTRIES,
            }
            for key, fmt in list_formats().items()
        ]
        schema["trained_chemistries"] = sorted(TRAINED_CHEMISTRIES)
        schema["telemetry_columns"] = sorted(TELEMETRY_COLUMNS)
        return _json_safe(schema)

    def _run_onboarding(body: Dict):
        mode = body.get("mode", "questionnaire")
        try:
            if mode == "telemetry":
                csv_text = body.get("csv")
                if not csv_text:
                    return None, ("No CSV content supplied.", 400)
                row, tier, assumptions = from_telemetry_csv(
                    csv_text,
                    format_key=body.get("format_key", ""),
                    battery_id=body.get("battery_id") or "USER-BATTERY",
                    ambient_temp_c=body.get("ambient_temp_c"),
                    re_ohm=body.get("re_ohm"),
                    rct_ohm=body.get("rct_ohm"),
                )
            elif mode == "questionnaire":
                row, tier, assumptions = from_questionnaire(body)
            else:
                return None, (f"Unknown mode {mode!r}.", 400)
        except OnboardingError as exc:
            return None, (str(exc), 400)
        except KeyError as exc:
            return None, (str(exc).strip("'\""), 400)

        measured = body.get("measured_capacity_ah")
        try:
            measured = float(measured) if measured not in (None, "") else None
        except (TypeError, ValueError):
            measured = None

        assessment = get_unseen().assess(
            row, tier, assumptions, measured_capacity_ah=measured
        )
        return assessment, None

    @app.post("/api/onboarding/assess")
    def onboarding_assess(body: Optional[Dict] = Body(None)):
        assessment, error = _run_onboarding(body or {})
        if error:
            message, status = error
            raise HTTPException(status_code=status, detail=message)
        return _json_safe(assessment)

    @app.post("/api/onboarding/passport")
    def onboarding_passport(body: Optional[Dict] = Body(None)):
        assessment, error = _run_onboarding(body or {})
        if error:
            message, status = error
            raise HTTPException(status_code=status, detail=message)
        document = get_unseen().issue_passport(assessment, private_key)
        return _json_safe(document)

    @app.post("/api/onboarding/format")
    def onboarding_register_format(body: Optional[Dict] = Body(None)):
        try:
            fmt = register_custom_format(body or {})
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _json_safe({
            "registered": True,
            "format": fmt.as_dict(),
            "in_training_distribution": fmt.chemistry in TRAINED_CHEMISTRIES,
        })

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "Invalid request body or parameters."},
        )

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    # API routes must be registered before the catch-all frontend mount.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR,
              html=True), name="frontend")
    return app


app = create_app()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the FastAPI server.")
    parser.add_argument("--data", type=Path, default=CYCLES_PATH)
    parser.add_argument("--models", type=Path, default=MODELS_DIR)
    parser.add_argument("--keys", type=Path, default=KEYS_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    app_instance = create_app(args.data, args.models, args.keys)
    logger.info(
        "BATRIS - Battery Traceability & Reliability Intelligence System")
    logger.info("http://%s:%d", args.host, args.port)
    uvicorn.run(app_instance, host=args.host,
                port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())