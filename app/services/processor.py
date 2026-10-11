"""
File processing orchestrator.

Coordinates file parsing, measurement calculation, and database persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from shapely.wkt import loads as from_wkt

from app.models.file import GeoFile, FileStatus
from app.models.feature import GeoFeature
from app.services.parser import parse_shapefile, parse_kml
from app.services.measurement import calculate_measurements

logger = logging.getLogger(__name__)


def process_geo_file(db: Session, geo_file: GeoFile) -> None:
    """
    Parse the uploaded file, compute measurements for every feature,
    and persist the results to the database.

    Updates geo_file.status to COMPLETED or FAILED in-place.
    """
    geo_file.status = FileStatus.PROCESSING
    db.commit()

    try:
        file_path = geo_file.file_path
        file_type = geo_file.file_type

        # --- Parse ---
        if file_type == "shapefile":
            raw_features, crs_string = parse_shapefile(file_path)
        elif file_type == "kml":
            raw_features, crs_string = parse_kml(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        geo_file.crs = crs_string
        geo_file.feature_count = len(raw_features)

        # --- Measure & persist features ---
        for feat in raw_features:
            geom_wkt = feat.get("geometry_wkt")
            geom_type = feat.get("geometry_type")
            crs = feat.get("crs") or crs_string or "EPSG:4326"

            area_m2 = None
            length_m = None

            if geom_wkt:
                try:
                    geom = from_wkt(geom_wkt)
                    area_m2, length_m = calculate_measurements(geom, crs)
                except Exception as exc:
                    logger.warning(
                        "Measurement failed for feature %d: %s",
                        feat["feature_index"],
                        exc,
                    )

            db_feature = GeoFeature(
                geo_file_id=geo_file.id,
                feature_index=feat["feature_index"],
                geometry_type=geom_type,
                geometry_wkt=geom_wkt,
                crs=crs,
                area_m2=area_m2,
                length_m=length_m,
                properties=feat.get("properties"),
            )
            db.add(db_feature)

        geo_file.status = FileStatus.COMPLETED
        geo_file.processed_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.error("Processing failed for file %s: %s", geo_file.id, exc, exc_info=True)
        geo_file.status = FileStatus.FAILED
        geo_file.error_message = str(exc)

    finally:
        db.commit()
