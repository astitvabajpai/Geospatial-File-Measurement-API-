from pydantic import BaseModel
from typing import Optional, Any


class FeatureMeasurement(BaseModel):
    feature_index: int
    geometry_type: Optional[str] = None
    geometry_wkt: Optional[str] = None
    crs: Optional[str] = None
    properties: Optional[dict[str, Any]] = None

    # Measurements — None when geometry type doesn't support them
    area_m2: Optional[float] = None
    length_m: Optional[float] = None

    model_config = {"from_attributes": True}


class MeasurementsResponse(BaseModel):
    file_id: str
    filename: str
    crs: Optional[str] = None
    feature_count: int
    features: list[FeatureMeasurement]
