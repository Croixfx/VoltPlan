from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

def normalize_database_url(url: str) -> str:
    """Hosting platforms hand out `postgres://...` or `postgresql://...`. SQLAlchemy rejects the first and (since 2.1)
    picks a different default driver for the second, so name the driver we install (psycopg2) explicitly."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from sqlalchemy import text
    import app.models.project  # noqa: F401
    import app.models.analysis  # noqa: F401
    import app.models.material  # noqa: F401
    import app.models.plan_file  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Lightweight additive column migrations for existing SQLite databases
    additions = {
        "analyses": {
            "canonical_geometry_data": "JSON",
            "geometry_reviewed": "BOOLEAN DEFAULT 0",
            "geometry_dirty": "BOOLEAN DEFAULT 0",
            "geometry_issues_data": "JSON",
        },
        "projects": {"scale_mm_per_pixel": "FLOAT", "scale_calibration": "JSON"},
        "plan_files": {"original_sha256": "VARCHAR(64)"},
    }
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            for table, columns in additions.items():
                existing = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
                if not existing:
                    continue
                for name, ddl in columns.items():
                    if name not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        else:
            from sqlalchemy import inspect

            existing = {column["name"] for column in inspect(conn).get_columns("plan_files")}
            if "original_sha256" not in existing:
                conn.execute(text("ALTER TABLE plan_files ADD COLUMN original_sha256 VARCHAR(64)"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_plan_files_original_sha256 "
            "ON plan_files (original_sha256)"
        ))
