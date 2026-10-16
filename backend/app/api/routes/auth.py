import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import (
    MIN_PASSWORD_LENGTH,
    auth_enabled,
    create_token,
    get_current_user,
    hash_password,
    is_valid_email,
    normalise_email,
    verify_password,
)
from app.core.config import settings
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])

# Failed sign-ins per email, to make guessing a password slow. In memory: it resets when the server restarts, which
# is acceptable for a single small instance.
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
_failures: Dict[str, Deque[float]] = defaultdict(deque)


class Credentials(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=200)
    name: Optional[str] = Field(None, max_length=255)


def _require_enabled() -> None:
    if not auth_enabled():
        raise HTTPException(status_code=503, detail="Sign-in is not switched on for this server.")


def _too_many_failures(email: str, now: float) -> bool:
    recent = _failures[email]
    while recent and recent[0] < now - WINDOW_SECONDS:
        recent.popleft()
    return len(recent) >= MAX_FAILURES


def _session(user: User) -> dict:
    return {"access_token": create_token(user), "token_type": "bearer",
            "user": {"id": user.id, "email": user.email, "name": user.name}}


def _adopt_legacy_projects(user: User, db: Session) -> None:
    """Projects made before accounts existed have no owner. The configured legacy owner receives them."""
    legacy = normalise_email(settings.LEGACY_OWNER_EMAIL)
    if legacy and user.email == legacy:
        db.query(Project).filter(Project.owner_id.is_(None)).update({Project.owner_id: user.id})
        db.commit()


@router.post("/register", status_code=201)
def register(data: Credentials, db: Session = Depends(get_db)):
    _require_enabled()
    email = normalise_email(data.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail=f"Use a password of at least {MIN_PASSWORD_LENGTH} characters.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")

    user = User(email=email, name=(data.name or "").strip(), password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _adopt_legacy_projects(user, db)
    return _session(user)


@router.post("/login")
def login(data: Credentials, db: Session = Depends(get_db)):
    _require_enabled()
    email = normalise_email(data.email)
    now = time.time()
    if _too_many_failures(email, now):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = db.query(User).filter(User.email == email).first()
    # Hash even for an unknown email so the answer takes the same time either way.
    stored = user.password_hash if user else hash_password("not-a-real-password")
    if not verify_password(data.password, stored) or user is None:
        _failures[email].append(now)
        raise HTTPException(status_code=401, detail="Wrong email or password.")

    _failures.pop(email, None)
    _adopt_legacy_projects(user, db)
    return _session(user)


@router.get("/me")
def me(user: Optional[User] = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=503, detail="Sign-in is not switched on for this server.")
    return {"id": user.id, "email": user.email, "name": user.name}
