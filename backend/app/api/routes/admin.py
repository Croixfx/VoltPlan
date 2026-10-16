"""Administrator overview: every account and every project, plus switching accounts off and on.

Admins are the emails listed in ADMIN_EMAILS. Opening, editing or deleting any project goes through the normal
project routes, which let admins past the ownership check.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.auth import is_admin, require_admin
from app.db.database import get_db
from app.models.analysis import Analysis
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


class Deactivation(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    by_status = dict(db.query(Project.status, func.count(Project.id)).group_by(Project.status).all())
    analyses = dict(db.query(Analysis.status, func.count(Analysis.id)).group_by(Analysis.status).all())
    return {
        "users": db.query(func.count(User.id)).scalar() or 0,
        "new_users_7d": db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0,
        "deactivated_users": db.query(func.count(User.id)).filter(User.deactivated_at.isnot(None)).scalar() or 0,
        "projects": db.query(func.count(Project.id)).scalar() or 0,
        "new_projects_7d": db.query(func.count(Project.id)).filter(Project.created_at >= week_ago).scalar() or 0,
        "unowned_projects": db.query(func.count(Project.id)).filter(Project.owner_id.is_(None)).scalar() or 0,
        "projects_by_status": by_status,
        "analyses_by_status": analyses,
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    counts = dict(db.query(Project.owner_id, func.count(Project.id)).group_by(Project.owner_id).all())
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "created_at": _iso(u.created_at),
            "is_admin": is_admin(u),
            "deactivated_at": _iso(u.deactivated_at),
            "deactivated_reason": u.deactivated_reason,
            "project_count": counts.get(u.id, 0),
        }
        for u in users
    ]


@router.get("/projects")
def list_all_projects(
    q: Optional[str] = Query(None, description="Search by name, client, location or owner email"),
    db: Session = Depends(get_db),
):
    query = db.query(Project, User.email).outerjoin(User, User.id == Project.owner_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Project.name.ilike(like), Project.client.ilike(like),
                                 Project.location.ilike(like), User.email.ilike(like)))
    rows = query.order_by(Project.created_at.desc()).limit(500).all()
    statuses = dict(db.query(Analysis.project_id, Analysis.status).all())
    return [
        {
            "id": p.id,
            "name": p.name,
            "client": p.client,
            "location": p.location,
            "status": p.status,
            "analysis_status": statuses.get(p.id),
            "owner_id": p.owner_id,
            "owner_email": email,
            "has_plan": bool(p.floor_plan_name),
            "created_at": _iso(p.created_at),
            "updated_at": _iso(p.updated_at),
        }
        for p, email in rows
    ]


def _target(user_id: str, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return user


@router.post("/users/{user_id}/deactivate")
def deactivate(user_id: str, data: Deactivation, db: Session = Depends(get_db)):
    user = _target(user_id, db)
    if is_admin(user):
        raise HTTPException(status_code=400, detail="An administrator account cannot be deactivated.")
    user.deactivated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.deactivated_reason = (data.reason or "").strip() or None
    db.commit()
    return {"id": user.id, "deactivated": True}


@router.post("/users/{user_id}/reactivate")
def reactivate(user_id: str, db: Session = Depends(get_db)):
    user = _target(user_id, db)
    user.deactivated_at = None
    user.deactivated_reason = None
    db.commit()
    return {"id": user.id, "deactivated": False}
