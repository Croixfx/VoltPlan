from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
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

    Base.metadata.create_all(bind=engine)

    # Lightweight additive column migrations for existing SQLite databases
    additions = {
        "analyses": {"canonical_geometry_data": "JSON"},
        "projects": {"scale_mm_per_pixel": "FLOAT", "scale_calibration": "JSON"},
    }
    try:
        with engine.connect() as conn:
            for table, columns in additions.items():
                existing = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
                if not existing:
                    continue
                for name, ddl in columns.items():
                    if name not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            conn.commit()
    except Exception:
        pass
