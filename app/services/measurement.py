"""
Measurement calculations for geospatial features.

All measurements are performed on projected (metric) geometries.
Supported types and their measurements:
  - Polygon / MultiPolygon  → area in square metres (m²)
  - LineString / MultiLineString → length in metres (m)
  - Point / MultiPoint → no measurement
  - Other types (GeometryCollection, etc.) → handled gracefully, no measurement
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from shapely.geometry.base import BaseGeometry

from app.services.crs import choose_projected_crs, reproject_geometry

logger = logging.getLogger(__name__)

# Geometry types that support specific measurements
_POLYGON_TYPES = {"Polygon", "MultiPolygon"}
_LINESTRING_TYPES = {"LineString", "MultiLineString", "LinearRing"}
_POINT_TYPES = {"Point", "MultiPoint"}


def calculate_measurements(
    geometry: BaseGeometry,
    source_crs: str,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate area and/or length for a geometry.

    Returns:
        (area_m2, length_m) — values are None when not applicable.
    """
    if geometry is None or geometry.is_empty:
        return None, None

    geom_type = geometry.geom_type

    if geom_type in _POINT_TYPES:
        # No measurement for points
        return None, None

    if geom_type not in _POLYGON_TYPES and geom_type not in _LINESTRING_TYPES:
        logger.info("Geometry type '%s' is not supported for measurement.", geom_type)
        return None, None

    # Reproject to a metric CRS
    try:
        projected_crs = choose_projected_crs(geometry, source_crs)
        projected_geom = reproject_geometry(geometry, source_crs, projected_crs)
    except ValueError as exc:
        logger.warning("CRS reprojection failed: %s", exc)
        return None, None

    area_m2: Optional[float] = None
    length_m: Optional[float] = None

    if geom_type in _POLYGON_TYPES:
        try:
            area_m2 = projected_geom.area
        except Exception as exc:
            logger.warning("Area calculation failed: %s", exc)

    if geom_type in _LINESTRING_TYPES:
        try:
            length_m = projected_geom.length
        except Exception as exc:
            logger.warning("Length calculation failed: %s", exc)

    return area_m2, length_m
