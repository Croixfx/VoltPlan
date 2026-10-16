from sqlalchemy import Column, String, LargeBinary, ForeignKey
from app.db.database import Base


class PlanFile(Base):
    """The uploaded drawing itself, kept in the database.

    Free hosting wipes the container's disk whenever the service restarts or sleeps, so the files under
    UPLOAD_DIR are only a cache; this row is the copy that survives (see app.services.plan_storage).
    """

    __tablename__ = "plan_files"

    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    original_name = Column(String(255), nullable=True)
    original_bytes = Column(LargeBinary, nullable=False)
    display_png_bytes = Column(LargeBinary, nullable=True)
    original_sha256 = Column(String(64), nullable=True, index=True)
