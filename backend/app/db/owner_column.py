"""Adds `projects.owner_id` to a database created before accounts existed.

Kept apart from init_db's SQLite-only migration so it also covers PostgreSQL (the production database).
"""
from sqlalchemy import inspect, text

from app.db.database import engine


def ensure_owner_column() -> None:
    with engine.begin() as conn:
        columns = {c["name"] for c in inspect(conn).get_columns("projects")}
        if "owner_id" not in columns:
            conn.execute(text("ALTER TABLE projects ADD COLUMN owner_id VARCHAR(36)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)"))

        user_columns = {c["name"] for c in inspect(conn).get_columns("users")}
        if "is_admin" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
        if "deactivated_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN deactivated_at TIMESTAMP"))
        if "deactivated_reason" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN deactivated_reason TEXT"))
