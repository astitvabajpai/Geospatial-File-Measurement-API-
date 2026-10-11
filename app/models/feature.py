from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class GeoFeature(Base):
    __tablename__ = "geo_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    geo_file_id = Column(String, ForeignKey("geo_files.id"), nullable=False)

    feature_index = Column(Integer, nullable=False)   # 0-based index from source file
    geometry_type = Column(String, nullable=True)     # Point / LineString / Polygon / etc.
    geometry_wkt = Column(String, nullable=True)      # WKT of original geometry
    crs = Column(String, nullable=True)               # CRS inherited from file

    # Measurements (None if not applicable)
    area_m2 = Column(Float, nullable=True)            # Polygon area in square metres
    length_m = Column(Float, nullable=True)           # LineString length in metres

    properties = Column(JSON, nullable=True)          # Original feature attributes

    geo_file = relationship("GeoFile", back_populates="features")
