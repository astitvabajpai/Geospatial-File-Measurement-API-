"""
Geospatial file parsers.

Supports:
  - .zip  containing a Shapefile (uses Fiona)
  - .kml  (parsed directly with Python stdlib xml — no GDAL/libkml needed)

Each parser returns a list of dicts with keys:
  feature_index, geometry_type, geometry_wkt, crs, properties
"""

from __future__ import annotations

import logging
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import fiona
from shapely.geometry import shape, Point, LineString, Polygon
from shapely.wkt import dumps as to_wkt

from app.services.crs import normalize_crs_string

logger = logging.getLogger(__name__)

FeatureDict = dict

# KML is always WGS 84 per the OGC spec
_KML_CRS = "EPSG:4326"

# XML namespaces used in KML files
_KML_NS = {
    "kml22": "http://www.opengis.net/kml/2.2",
    "kml21": "http://earth.google.com/kml/2.1",
    "kml20": "http://earth.google.com/kml/2.0",
}


# ── helpers ────────────────────────────────────────────────────────────────

def _geometry_to_wkt(geom_dict: dict | None) -> str | None:
    """Convert a GeoJSON-like geometry dict to WKT string."""
    if geom_dict is None:
        return None
    try:
        return to_wkt(shape(geom_dict))
    except Exception as exc:
        logger.warning("Failed to convert geometry to WKT: %s", exc)
        return None


def _sanitize_properties(props: dict) -> dict:
    """Convert fiona property values to JSON-serialisable types."""
    result = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            result[k] = v
        else:
            result[k] = str(v)
    return result


# ── Shapefile parser (via Fiona) ───────────────────────────────────────────

def parse_shapefile(zip_path: str) -> tuple[list[FeatureDict], str | None]:
    """Extract and parse a zipped Shapefile. Returns (features, crs_string)."""
    tmp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        shp_files = list(Path(tmp_dir).rglob("*.shp"))
        if not shp_files:
            raise ValueError("No .shp file found inside the ZIP archive.")

        return _read_with_fiona(str(shp_files[0]))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _read_with_fiona(path: str) -> tuple[list[FeatureDict], str | None]:
    """Generic Fiona reader for any OGR-supported format."""
    features: list[FeatureDict] = []
    crs_string: str | None = None

    with fiona.open(path, "r") as src:
        raw_crs = src.crs
        if raw_crs:
            try:
                crs_string = normalize_crs_string(raw_crs)
            except Exception:
                crs_string = str(raw_crs)
        if not crs_string:
            crs_string = "EPSG:4326"

        for idx, feature in enumerate(src):
            geom_dict = feature.get("geometry")
            geom_type = geom_dict.get("type") if geom_dict else None
            wkt = _geometry_to_wkt(geom_dict)
            props = _sanitize_properties(dict(feature.get("properties") or {}))
            features.append({
                "feature_index": idx,
                "geometry_type": geom_type,
                "geometry_wkt": wkt,
                "crs": crs_string,
                "properties": props,
            })

    return features, crs_string


# ── KML parser (stdlib xml — no GDAL/libkml needed) ───────────────────────

def _parse_coords(coord_text: str) -> list[tuple[float, float]]:
    """Parse a KML <coordinates> string into a list of (lon, lat) tuples."""
    points = []
    for token in coord_text.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            points.append((lon, lat))
    return points


def _detect_ns(root: ET.Element) -> str:
    """Return the KML namespace string detected from the root element tag."""
    tag = root.tag
    if tag.startswith("{"):
        return tag[1: tag.index("}")]
    return ""


def _find_text(el: ET.Element, tag: str, ns: str) -> str | None:
    """Find a child element's text with optional namespace."""
    child = el.find(f"{{{ns}}}{tag}" if ns else tag)
    return child.text.strip() if child is not None and child.text else None


def _extract_geometry(placemark: ET.Element, ns: str):
    """
    Extract a Shapely geometry from a KML <Placemark>.
    Supports: Point, LineString, Polygon, MultiGeometry.
    Returns None if no geometry is found.
    """
    prefix = f"{{{ns}}}" if ns else ""

    # --- Point ---
    pt_el = placemark.find(f"{prefix}Point")
    if pt_el is not None:
        coords_el = pt_el.find(f"{prefix}coordinates")
        if coords_el is not None and coords_el.text:
            pts = _parse_coords(coords_el.text)
            if pts:
                return Point(pts[0])

    # --- LineString ---
    ls_el = placemark.find(f"{prefix}LineString")
    if ls_el is not None:
        coords_el = ls_el.find(f"{prefix}coordinates")
        if coords_el is not None and coords_el.text:
            pts = _parse_coords(coords_el.text)
            if len(pts) >= 2:
                return LineString(pts)

    # --- Polygon ---
    poly_el = placemark.find(f"{prefix}Polygon")
    if poly_el is not None:
        outer = poly_el.find(f".//{prefix}outerBoundaryIs//{prefix}coordinates")
        if outer is not None and outer.text:
            shell = _parse_coords(outer.text)
            holes = []
            for inner in poly_el.findall(f".//{prefix}innerBoundaryIs//{prefix}coordinates"):
                if inner.text:
                    holes.append(_parse_coords(inner.text))
            if len(shell) >= 3:
                return Polygon(shell, holes)

    # --- MultiGeometry (recurse) ---
    multi_el = placemark.find(f"{prefix}MultiGeometry")
    if multi_el is not None:
        from shapely.geometry import GeometryCollection
        geoms = []
        for child in multi_el:
            # wrap each child in a fake placemark and recurse
            fake = ET.Element("Placemark")
            fake.append(child)
            g = _extract_geometry(fake, ns)
            if g:
                geoms.append(g)
        if geoms:
            return GeometryCollection(geoms)

    return None


def parse_kml(kml_path: str) -> tuple[list[FeatureDict], str]:
    """
    Parse a KML file using Python's stdlib xml parser.
    No GDAL/libkml required.
    Returns (features, "EPSG:4326").
    """
    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = _detect_ns(root)
    prefix = f"{{{ns}}}" if ns else ""

    features: list[FeatureDict] = []
    idx = 0

    for placemark in root.iter(f"{prefix}Placemark"):
        name = _find_text(placemark, "name", ns) or ""
        description = _find_text(placemark, "description", ns) or ""

        # Collect <ExtendedData> <Data> entries as properties
        props: dict = {"name": name, "description": description}
        ext_data = placemark.find(f"{prefix}ExtendedData")
        if ext_data is not None:
            for data_el in ext_data.findall(f"{prefix}Data"):
                key = data_el.get("name", "")
                val_el = data_el.find(f"{prefix}value")
                if key and val_el is not None:
                    props[key] = val_el.text or ""

        geom = _extract_geometry(placemark, ns)
        geom_type = geom.geom_type if geom else None
        wkt = to_wkt(geom) if geom else None

        features.append({
            "feature_index": idx,
            "geometry_type": geom_type,
            "geometry_wkt": wkt,
            "crs": _KML_CRS,
            "properties": props,
        })
        idx += 1

    return features, _KML_CRS
