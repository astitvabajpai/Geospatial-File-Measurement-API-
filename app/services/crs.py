"""
CRS handling utilities.

Strategy for choosing a projected CRS:
  - For global or large extents we use the Equal Earth projection (EPSG:8857),
    which gives accurate area/length calculations worldwide.
  - For smaller regional extents (bounding box fits within a UTM zone) we pick
    the appropriate UTM zone, which is even more accurate locally.
  - If pyproj cannot identify the source CRS we fall back to EPSG:8857.

We avoid calculating measurements directly in geographic (lat/lon) coordinates
because degree-based distances / areas are not meaningful physical quantities.
"""

from __future__ import annotations

import logging
from typing import Optional

from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

logger = logging.getLogger(__name__)

# Fallback global equal-area projection
_FALLBACK_CRS = "EPSG:8857"  # Equal Earth


def _utm_epsg_from_lon_lat(lon: float, lat: float) -> str:
    """Return the EPSG code for the UTM zone that contains the given point."""
    zone_number = int((lon + 180) / 6) + 1
    if lat >= 0:
        epsg = 32600 + zone_number  # WGS 84 / UTM north
    else:
        epsg = 32700 + zone_number  # WGS 84 / UTM south
    return f"EPSG:{epsg}"


def choose_projected_crs(geometry: BaseGeometry, source_crs_str: str) -> str:
    """
    Given a geometry and its source CRS string, return an appropriate
    projected CRS EPSG string for accurate metric measurements.
    """
    try:
        src_crs = CRS.from_user_input(source_crs_str)
    except Exception:
        logger.warning("Could not parse source CRS '%s', using fallback.", source_crs_str)
        return _FALLBACK_CRS

    # If source is already projected (not geographic) use it directly
    if not src_crs.is_geographic:
        return source_crs_str

    # Try to use the centroid to pick a UTM zone (works when source is lat/lon)
    try:
        centroid = geometry.centroid
        lon, lat = centroid.x, centroid.y
        # Clamp to valid UTM range
        if -180 <= lon <= 180 and -80 <= lat <= 84:
            return _utm_epsg_from_lon_lat(lon, lat)
    except Exception:
        pass

    return _FALLBACK_CRS


def reproject_geometry(
    geometry: BaseGeometry,
    source_crs_str: str,
    target_crs_str: str,
) -> BaseGeometry:
    """Reproject a Shapely geometry from source_crs to target_crs."""
    try:
        src_crs = CRS.from_user_input(source_crs_str)
        tgt_crs = CRS.from_user_input(target_crs_str)
        transformer = Transformer.from_crs(src_crs, tgt_crs, always_xy=True)
        return transform(transformer.transform, geometry)
    except Exception as exc:
        raise ValueError(
            f"Failed to reproject geometry from {source_crs_str} to {target_crs_str}: {exc}"
        ) from exc


def normalize_crs_string(crs_input) -> Optional[str]:
    """Convert any pyproj-compatible CRS input to a clean 'EPSG:XXXX' string if possible."""
    if crs_input is None:
        return None
    try:
        crs = CRS.from_user_input(crs_input)
        authority = crs.to_authority()
        if authority:
            return f"{authority[0]}:{authority[1]}"
        return crs.to_string()
    except Exception:
        return str(crs_input)
