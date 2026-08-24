"""Small, dependency-light MongoDB-backed authentication for the BATRIS web app.

The battery-analysis endpoints remain unchanged; this module only owns user
accounts, sessions, and durable user history.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.errors import DuplicateKeyError
except ImportError:  # pragma: no cover - dependency is installed in deployment
    ASCENDING = 1
    DESCENDING = -1
    MongoClient = None  # type: ignore[assignment]

    class DuplicateKeyError(Exception):
        pass

SESSION_COOKIE = "batris_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        candidate = _password_hash(password, _unb64(salt_b64))
        return hmac.compare_digest(candidate, stored)
    except (ValueError, TypeError):
        return False


def _session_secret() -> bytes:
    raw = os.getenv("BATRIS_AUTH_SECRET", "").strip()
    if len(raw) < 32:
        raise RuntimeError(
            "BATRIS_AUTH_SECRET must be set to a random value of at least 32 characters."
        )
    return raw.encode("utf-8")


def _make_session(user_id: str) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    nonce = secrets.token_urlsafe(12)
    payload = f"{user_id}.{expires}.{nonce}".encode("utf-8")
    signature = hmac.new(_session_secret(), payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(signature)}"


def _read_session(token: str | None) -> Optional[str]:
    if not token:
        return None
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload = _unb64(payload_b64)
        expected = hmac.new(_session_secret(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature_b64)):
            return None
        user_id, expires, _nonce = payload.decode("utf-8").split(".", 2)
        if int(expires) < int(time.time()):
            return None
        return user_id
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthStore:
    def __init__(self) -> None:
        if MongoClient is None:
            raise RuntimeError("MongoDB support requires the `pymongo` package. Run `pip install -r requirements.txt`.")
        uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
        database_name = os.getenv("MONGODB_DB_NAME", "batris")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[database_name]
        self.users = self.db["users"]
        self.assessments = self.db["assessments"]
        self.passports = self.db["passports"]
        self.users.create_index([("email", ASCENDING)], unique=True)
        self.assessments.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self.passports.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)]
        )
        self.passports.create_index(
            [("user_id", ASCENDING), ("passport_id", ASCENDING)], unique=True
        )

    @staticmethod
    def _public_user(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc["_id"]),
            "name": doc.get("name", ""),
            "email": doc.get("email", ""),
            "created_at": doc.get("created_at"),
        }

    def create_user(self, name: str, email: str, password: str) -> Dict[str, Any]:
        now = _utc_now().isoformat()
        doc = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": _password_hash(password),
            "created_at": now,
        }
        try:
            result = self.users.insert_one(doc)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
        doc["_id"] = result.inserted_id
        return self._public_user(doc)

    def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        doc = self.users.find_one({"email": email.strip().lower()})
        if not doc or not _verify_password(password, doc.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        return self._public_user(doc)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            from bson import ObjectId

            doc = self.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        return self._public_user(doc) if doc else None

    def save_assessment(
        self,
        user_id: str,
        battery_id: str | None,
        input_mode: str,
        format_key: str | None,
        input_snapshot: Dict[str, Any],
        assessment: Dict[str, Any],
    ) -> None:
        self.assessments.insert_one(
            {
                "user_id": user_id,
                "battery_id": battery_id or "USER-BATTERY",
                "input_mode": input_mode,
                "format_key": format_key,
                "input_snapshot": input_snapshot,
                "assessment": assessment,
                "created_at": _utc_now().isoformat(),
            }
        )

    def list_assessments(self, user_id: str, limit: int = 25) -> list[Dict[str, Any]]:
        rows = self.assessments.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)
        out: list[Dict[str, Any]] = []
        for row in rows:
            row["id"] = str(row.pop("_id"))
            out.append(row)
        return out

    def save_passport(self, user_id: str, passport: Dict[str, Any]) -> bool:
        payload = passport.get("payload") or {}
        passport_id = payload.get("passport_id")
        if not passport_id:
            raise HTTPException(status_code=400, detail="Passport payload has no passport_id.")
        result = self.passports.update_one(
            {"user_id": user_id, "passport_id": passport_id},
            {
                "$set": {
                    "passport": passport,
                    "battery_id": (payload.get("battery") or {}).get("battery_id"),
                    "updated_at": _utc_now().isoformat(),
                },
                "$setOnInsert": {"created_at": _utc_now().isoformat()},
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def list_passports(self, user_id: str, limit: int = 25) -> list[Dict[str, Any]]:
        rows = self.passports.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(limit)
        out: list[Dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            out.append(row)
        return out


_store: AuthStore | None = None


def get_auth_store() -> AuthStore:
    global _store
    if _store is None:
        try:
            _store = AuthStore()
        except Exception as exc:  # surface configuration/connection failures cleanly
            raise HTTPException(
                status_code=503,
                detail=f"Account storage is unavailable: {exc}",
            ) from exc
    return _store


def set_session(response: Response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        _make_session(user_id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=os.getenv("BATRIS_COOKIE_SECURE", "0") == "1",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request) -> Optional[Dict[str, Any]]:
    user_id = _read_session(request.cookies.get(SESSION_COOKIE))
    if not user_id:
        return None
    try:
        return get_auth_store().get_user(user_id)
    except Exception:
        return None


def require_user(request: Request) -> Dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to access your account.")
    return user
