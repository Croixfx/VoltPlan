import uuid
from sqlalchemy import Column, String, Float
from app.db.database import Base


class MaterialItem(Base):
    __tablename__ = "materials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_code = Column(String(50), nullable=False, unique=True)
    category = Column(String(100), nullable=False)
    description = Column(String(255), nullable=False)
    specification = Column(String(255), nullable=False)
    unit = Column(String(20), nullable=False)
    unit_price_rwf = Column(Float, nullable=False)
    source = Column(String(100), nullable=False, default="Kigali Baseline 2025/2026")
