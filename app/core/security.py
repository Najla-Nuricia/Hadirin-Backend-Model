"""Password hashing (bcrypt) and stateless JWT signing/verification (PyJWT)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    if not plain_password:
        raise ValueError("Password tidak boleh kosong.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(
    subject: str,
    role: str = "mahasiswa",
    extra_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    """Create a signed HS256 JWT access token with expiration."""
    cfg = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=cfg.jwt_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "nim": subject,
        "role": role,
        "type": "access",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate an HS256 JWT access token."""
    cfg = settings or get_settings()
    if not token:
        raise UnauthorizedError("Token autentikasi wajib disertakan.")

    try:
        payload = jwt.decode(
            token,
            cfg.jwt_secret_key,
            algorithms=[cfg.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Sesi login telah berakhir. Silakan login ulang.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token autentikasi tidak valid.") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise UnauthorizedError("Payload token tidak valid.")

    return payload

