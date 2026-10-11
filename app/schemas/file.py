from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.file import FileStatus


class GeoFileResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    feature_count: Optional[int] = None
    crs: Optional[str] = None
    status: FileStatus
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
