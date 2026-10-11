"""
File API routes.

POST /api/files/                  — upload & process a geospatial file
GET  /api/files/{id}/             — retrieve file metadata
GET  /api/files/{id}/measurements/ — retrieve feature measurements
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.feature import GeoFeature
from app.models.file import GeoFile, FileStatus
from app.schemas.feature import FeatureMeasurement, MeasurementsResponse
from app.schemas.file import GeoFileResponse
from app.services.processor import process_geo_file

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXTENSION_TO_TYPE = {
    ".zip": "shapefile",
    ".kml": "kml",
}


def _detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in _EXTENSION_TO_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Accepted: .zip (Shapefile), .kml",
        )
    return _EXTENSION_TO_TYPE[suffix]


def _save_upload(upload: UploadFile) -> str:
    """Persist the uploaded file to disk and return the saved path."""
    unique_name = f"{uuid.uuid4()}_{upload.filename}"
    dest = Path(settings.UPLOAD_DIR) / unique_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with dest.open("wb") as f:
        while chunk := upload.file.read(1024 * 256):  # 256 KB chunks
            size += len(chunk)
            if size > settings.MAX_UPLOAD_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB.",
                )
            f.write(chunk)
    return str(dest)


def _get_file_or_404(file_id: str, db: Session) -> GeoFile:
    geo_file = db.query(GeoFile).filter(GeoFile.id == file_id).first()
    if not geo_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found.",
        )
    return geo_file


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=GeoFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
)
def upload_file(
    file: UploadFile = File(..., description="A .zip (Shapefile) or .kml file"),
    db: Session = Depends(get_db),
):
    """
    Upload a geospatial file for processing.

    - Accepts a **.zip** containing a Shapefile or a **.kml** file.
    - The file is processed synchronously; the response contains processing results.
    - Feature measurements are available immediately via the measurements endpoint.
    """
    file_type = _detect_file_type(file.filename)
    saved_path = _save_upload(file)

    geo_file = GeoFile(
        filename=file.filename,
        file_type=file_type,
        file_path=saved_path,
        status=FileStatus.PENDING,
    )
    db.add(geo_file)
    db.commit()
    db.refresh(geo_file)

    # Process synchronously (for simplicity; see README for async alternative)
    process_geo_file(db, geo_file)
    db.refresh(geo_file)

    return geo_file


@router.get(
    "/{file_id}/",
    response_model=GeoFileResponse,
    summary="Get file metadata",
)
def get_file(file_id: str, db: Session = Depends(get_db)):
    """
    Retrieve metadata about an uploaded file including its processing status,
    detected CRS, and feature count.
    """
    return _get_file_or_404(file_id, db)


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get feature measurements",
)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    """
    Retrieve measurements for every feature in the uploaded file.

    - **Polygon / MultiPolygon**: area in m²
    - **LineString / MultiLineString**: length in metres
    - **Point**: no measurement (null values)
    - Unsupported geometry types are returned with null measurements (no crash).
    """
    geo_file = _get_file_or_404(file_id, db)

    if geo_file.status == FileStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File processing failed: {geo_file.error_message}",
        )

    if geo_file.status in (FileStatus.PENDING, FileStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="File is still being processed. Try again shortly.",
        )

    features = (
        db.query(GeoFeature)
        .filter(GeoFeature.geo_file_id == file_id)
        .order_by(GeoFeature.feature_index)
        .all()
    )

    return MeasurementsResponse(
        file_id=geo_file.id,
        filename=geo_file.filename,
        crs=geo_file.crs,
        feature_count=geo_file.feature_count or 0,
        features=[FeatureMeasurement.model_validate(f) for f in features],
    )
