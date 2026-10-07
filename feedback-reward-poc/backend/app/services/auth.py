"""Staff authentication: setup, login, logout, session validation.

- Password hashing: Argon2id (argon2-cffi).
- Sessions: opaque random token; sha256 hash stored in `staff_sessions`.
- Setup is permitted only when no staff user exists yet.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.db import mongo

_hasher = PasswordHasher()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def setup_required() -> bool:
    return mongo.staff_users_collection().count_documents({}) == 0


def create_first_admin(username: str, password: str) -> dict:
    user = {
        "_id": "admin",
        "id": 1,
        "username": username,
        "password_hash": _hasher.hash(password),
        "role": "admin",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        mongo.staff_users_collection().insert_one(user)
    except DuplicateKeyError as exc:
        raise ValueError("Admin account already exists.") from exc
    return user


def login(username: str, password: str) -> tuple[str, datetime] | None:
    user = mongo.staff_users_collection().find_one({"username": username})
    if user is None:
        return None
    try:
        _hasher.verify(user["password_hash"], password)
    except (VerificationError, VerifyMismatchError):
        return None
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
    mongo.staff_sessions_collection().insert_one({
        "token_hash": _hash_token(token),
        "user_id": user["id"],
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
    })
    return token, expires_at


def logout(token: str | None) -> None:
    if not token:
        return
    mongo.staff_sessions_collection().delete_one({"token_hash": _hash_token(token)})


def current_user(token: str | None) -> dict | None:
    if not token:
        return None
    now = datetime.now(timezone.utc)
    session = mongo.staff_sessions_collection().find_one({
        "token_hash": _hash_token(token), "expires_at": {"$gt": now},
    })
    if session is None:
        return None
    return mongo.staff_users_collection().find_one({"id": session["user_id"]}, {"_id": 0})
