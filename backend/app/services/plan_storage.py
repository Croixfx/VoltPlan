"""Keeps uploaded drawings alive across server restarts.

The drawing is written to disk on upload (everything else reads it from there) and a copy is stored in the
database. When the disk copy has been wiped, it is rebuilt from the database the next time it is needed.
"""
import hashlib
import os

from sqlalchemy.orm import Session, object_session

from app.core.logging import logger
from app.models.plan_file import PlanFile
from app.models.project import Project


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def display_path_for(project: Project) -> str:
    return os.path.join(os.path.dirname(project.floor_plan_path), "display_plan.png")


def store_plan(db: Session, project: Project) -> None:
    """Save (or replace) the database copy of the project's drawing. Call after the files are on disk."""
    display = display_path_for(project)
    row = db.get(PlanFile, project.id)
    if row is None:
        row = PlanFile(project_id=project.id, original_bytes=b"")
        db.add(row)
    row.original_name = project.floor_plan_name
    row.original_bytes = _read(project.floor_plan_path)
    row.original_sha256 = hashlib.sha256(row.original_bytes).hexdigest()
    row.display_png_bytes = _read(display) if os.path.exists(display) else None


def ensure_plan_on_disk(project: Project, db: Session | None = None) -> bool:
    """True when the drawing is available on disk, rebuilding it from the database if the disk was wiped."""
    if not project.floor_plan_path:
        return False
    display = display_path_for(project)
    if os.path.exists(project.floor_plan_path) and os.path.exists(display):
        return True

    db = db or object_session(project)
    row = db.get(PlanFile, project.id) if db is not None else None
    if row is None:
        return os.path.exists(project.floor_plan_path)

    os.makedirs(os.path.dirname(project.floor_plan_path), exist_ok=True)
    if not os.path.exists(project.floor_plan_path):
        with open(project.floor_plan_path, "wb") as f:
            f.write(row.original_bytes)
    if row.display_png_bytes and not os.path.exists(display):
        with open(display, "wb") as f:
            f.write(row.display_png_bytes)
    logger.info(f"Restored the floor plan for project {project.id} from the database")
    return os.path.exists(project.floor_plan_path)
