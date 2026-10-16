"""Per-user login: password hashing, signed session tokens and the FastAPI dependencies that enforce them.

Tokens are stateless (an HMAC-signed payload with an expiry), so there is no session table; signing out simply
discards the token on the device. The signing secret is `AUTH_SECRET`, which must be different from the shared
`API_KEY`: the API key is embedded in the mobile app, so anyone can extract it.

When `AUTH_SECRET` is empty (local development and tests) login is switched off and every route behaves as it did
before accounts existed. Production refuses to start without it (see app.core.security).
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User

PBKDF2_ROUNDS = 390_000
MIN_PASSWORD_LENGTH = 8
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def auth_enabled() -> bool:
    return bool(settings.AUTH_SECRET)


def is_admin(user: Optional[User]) -> bool:
    if user is None:
        return False
    admins = {normalise_email(e) for e in settings.ADMIN_EMAILS.split(",") if e.strip()}
    return user.email in admins


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email)) and len(email) <= 255


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(rounds))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(settings.AUTH_SECRET.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())


def create_token(user: User, now: Optional[float] = None) -> str:
    issued = int(now if now is not None else time.time())
    body = _b64(json.dumps({"sub": user.id, "exp": issued + settings.AUTH_TOKEN_DAYS * 86400}).encode("utf-8"))
    return f"v1.{body}.{_sign('v1.' + body)}"


def read_token(token: str, now: Optional[float] = None) -> Optional[str]:
    """The user id a valid, unexpired token was issued to, else None."""
    if not auth_enabled():
        return None
    try:
        version, body, signature = token.split(".")
        if version != "v1" or not hmac.compare_digest(signature, _sign(f"{version}.{body}")):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < (now if now is not None else time.time()):
            return None
        return str(payload["sub"])
    except Exception:
        return None


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """The signed-in user, or None when login is switched off. Raises 401 when login is on and the request has no
    valid token."""
    if not auth_enabled():
        return None
    token = _bearer(authorization)
    user_id = read_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is not None and user.deactivated_at is not None:
        raise HTTPException(status_code=403, detail="This account has been deactivated. Contact the administrator.")
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: Optional[User] = Depends(get_current_user)) -> User:
    if user is None or not is_admin(user):
        raise HTTPException(status_code=403, detail="Administrators only.")
    return user


async def require_project_access(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Routes under /projects/{project_id}/...: the project must belong to the signed-in user. Someone else's
    project answers 404, exactly like one that does not exist."""
    project_id = request.path_params.get("project_id")
    if user is None or project_id is None or is_admin(user):
        return
    owner_id = db.query(Project.owner_id).filter(Project.id == project_id).scalar()
    if owner_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found.")
