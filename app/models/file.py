import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class FileStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GeoFile(Base):
    __tablename__ = "geo_files"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)          # "shapefile" | "kml"
    file_path = Column(String, nullable=False)          # path on disk
    feature_count = Column(Integer, nullable=True)
    crs = Column(String, nullable=True)                 # e.g. "EPSG:4326"
    status = Column(SAEnum(FileStatus), default=FileStatus.PENDING, nullable=False)
    error_message = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    features = relationship("GeoFeature", back_populates="geo_file", cascade="all, delete-orphan")
