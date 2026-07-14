"""
Layer 2 (JWT), Layer 3 (Agent HMAC token), Layer 5 (Command signature),
Layer 9 (Password hashing) all live here so every crypto decision in the
project is auditable from a single file.
"""
import hmac
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Layer 9 — Password hashing (Argon2id, bcrypt as fallback verifier)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Layer 2 — JWT access / refresh tokens
# ---------------------------------------------------------------------------
def _create_token(subject: str, expires_delta: timedelta, token_type: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_hex(16),  # unique id -> lets us revoke individual refresh tokens
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _create_token(user_id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def create_2fa_setup_token(user_id: str) -> str:
    """Short-lived token issued right after password verification, when the
    account still needs to complete mandatory 2FA enrollment. Deliberately
    not an access token — it only proves "you just entered the right
    password", not "you're fully logged in"."""
    return _create_token(user_id, timedelta(minutes=10), "2fa_setup")


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on failure — caller should turn that into a 401."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Layer 3 — Agent token (machine_id + 256-bit secret, HMAC challenge)
# ---------------------------------------------------------------------------
def generate_agent_secret() -> str:
    return secrets.token_hex(settings.AGENT_SECRET_BYTES)


def sign_agent_challenge(machine_id: str, secret: str, nonce: str) -> str:
    """
    The agent proves possession of its secret by HMAC-signing a server
    supplied nonce, instead of ever sending the raw secret over the wire.
    """
    msg = f"{machine_id}:{nonce}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_agent_challenge(machine_id: str, secret: str, nonce: str, signature: str) -> bool:
    expected = sign_agent_challenge(machine_id, secret, nonce)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Layer 5 — Command signature (anti-tamper + anti-replay)
# ---------------------------------------------------------------------------
def sign_command(machine_secret: str, command: str, timestamp: int, nonce: str) -> str:
    msg = f"{command}:{timestamp}:{nonce}".encode()
    return hmac.new(machine_secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_command_signature(
    machine_secret: str, command: str, timestamp: int, nonce: str, signature: str
) -> tuple[bool, str]:
    """Returns (is_valid, reason_if_invalid)."""
    now = int(time.time())
    if abs(now - timestamp) > settings.COMMAND_TIMESTAMP_SKEW_SECONDS:
        return False, "timestamp outside allowed skew (stale or clock drift)"

    expected = sign_command(machine_secret, command, timestamp, nonce)
    if not hmac.compare_digest(expected, signature):
        return False, "signature mismatch"

    return True, ""


def generate_nonce() -> str:
    return secrets.token_hex(16)


def generate_pair_code() -> str:
    """Human-typeable pairing code, e.g. ABCD-EFGH."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I)
    part = lambda n: "".join(secrets.choice(alphabet) for _ in range(n))
    return f"{part(4)}-{part(4)}"
