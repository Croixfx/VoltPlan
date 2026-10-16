import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, String, Text
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, unique=True, index=True)  # stored lower-case
    name = Column(String(255), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_admin = Column(Boolean, nullable=False, default=False)  # granted by another admin (ADMIN_EMAILS are always admins)
    deactivated_at = Column(DateTime, nullable=True)  # set by an admin: the account can no longer sign in or act
    deactivated_reason = Column(Text, nullable=True)
