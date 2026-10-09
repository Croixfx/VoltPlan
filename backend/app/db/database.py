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

    # Ensure canonical_geometry_data column exists on analyses table for SQLite
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(analyses)"))
            cols = [row[1] for row in result.fetchall()]
            if cols and "canonical_geometry_data" not in cols:
                conn.execute(text("ALTER TABLE analyses ADD COLUMN canonical_geometry_data JSON"))
                conn.commit()
    except Exception:
        pass
