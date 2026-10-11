# Geospatial File Measurement API

A FastAPI backend service that accepts geospatial files, processes the features within them, and returns measurement information. Built with Python 3.11+, FastAPI, SQLAlchemy, Fiona, Shapely, and pyproj.

---

## Setup

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/astitvabajpai/Geospatial-File-Measurement-API-.git
cd Geospatial-File-Measurement-API-

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Configure environment variables
cp .env.example .env
# Edit .env to change DATABASE_URL, UPLOAD_DIR, or MAX_UPLOAD_SIZE
```

### Running the application locally

```bash
uvicorn app.main:app --reload
```

The API runs at **http://127.0.0.1:8000**

Interactive docs (Swagger UI): **http://127.0.0.1:8000/docs**

Alternative docs (ReDoc): **http://127.0.0.1:8000/redoc**

---

## API

### Endpoints overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/files/` | Upload and process a geospatial file |
| GET | `/api/files/{id}/` | Get information about an uploaded file |
| GET | `/api/files/{id}/measurements/` | Get measurements for all features in a file |

---

### POST `/api/files/`

Upload a geospatial file. Accepted formats:
- `.zip` — ZIP archive containing a Shapefile (`.shp`, `.dbf`, `.prj`, etc.)
- `.kml` — Keyhole Markup Language file

The file is parsed and all features measured synchronously. The response is returned once processing is complete.

**Request** — `multipart/form-data`

```
file: <binary>
```

**Example requests:**

```bash
# Upload a Shapefile
curl -X POST "http://127.0.0.1:8000/api/files/" \
     -F "file=@survey.zip"

# Upload a KML file
curl -X POST "http://127.0.0.1:8000/api/files/" \
     -F "file=@roads.kml"
```

**Response `201 Created`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "survey.zip",
  "file_type": "shapefile",
  "feature_count": 42,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error_message": null,
  "uploaded_at": "2024-01-15T10:30:00",
  "processed_at": "2024-01-15T10:30:02"
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| `413` | File exceeds 50 MB limit |
| `415` | Unsupported file type (not `.zip` or `.kml`) |
| `422` | File could not be parsed (malformed or invalid content) |

---

### GET `/api/files/{id}/`

Returns information about an uploaded file.

**Example:**

```bash
curl "http://127.0.0.1:8000/api/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/"
```

**Response `200 OK`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "survey.kml",
  "file_type": "kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error_message": null,
  "uploaded_at": "2024-01-15T10:30:00",
  "processed_at": "2024-01-15T10:30:02"
}
```

**Status values:**

| Value | Meaning |
|-------|---------|
| `PENDING` | File received, not yet processed |
| `PROCESSING` | Parsing and measurement in progress |
| `COMPLETED` | Processing finished successfully |
| `FAILED` | Processing failed — see `error_message` |

**Error responses:**

| Status | Reason |
|--------|--------|
| `404` | File ID not found |

---

### GET `/api/files/{id}/measurements/`

Returns per-feature measurements for a processed file.

Measurement rules:
- **Polygon / MultiPolygon** → `area_m2` in square metres
- **LineString / MultiLineString** → `length_m` in metres
- **Point / MultiPoint** → both `area_m2` and `length_m` are `null`
- Any other geometry type → both values are `null` (handled gracefully, no error)

**Example:**

```bash
curl "http://127.0.0.1:8000/api/files/3fa85f64-5717-4562-b3fc-2c963f66afa6/measurements/"
```

**Response `200 OK`:**

```json
{
  "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "survey.kml",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "features": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "geometry_wkt": "POLYGON ((77.5 12.9, 77.6 12.9, 77.6 13.0, 77.5 13.0, 77.5 12.9))",
      "crs": "EPSG:4326",
      "properties": { "name": "Plot A", "owner": "Alice" },
      "area_m2": 120172105.92,
      "length_m": null
    },
    {
      "feature_index": 1,
      "geometry_type": "LineString",
      "geometry_wkt": "LINESTRING (77.5 12.9, 77.55 12.95, 77.6 13.0)",
      "crs": "EPSG:4326",
      "properties": { "name": "Road 1" },
      "area_m2": null,
      "length_m": 15504.49
    },
    {
      "feature_index": 2,
      "geometry_type": "Point",
      "geometry_wkt": "POINT (77.55 12.95)",
      "crs": "EPSG:4326",
      "properties": { "name": "Marker" },
      "area_m2": null,
      "length_m": null
    }
  ]
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| `404` | File ID not found |
| `202` | File is still being processed |
| `422` | File processing failed |

---

## Architecture

### Application structure

```
geospatial-api/
├── app/
│   ├── main.py                   # FastAPI app, CORS middleware, router registration, DB init
│   ├── core/
│   │   └── config.py             # Settings via pydantic-settings (.env support)
│   ├── db/
│   │   ├── base.py               # SQLAlchemy DeclarativeBase
│   │   └── session.py            # Engine creation, SessionLocal, get_db dependency
│   ├── models/
│   │   ├── file.py               # GeoFile ORM model (id, filename, crs, status, ...)
│   │   └── feature.py            # GeoFeature ORM model (geometry, measurements, properties)
│   ├── schemas/
│   │   ├── file.py               # GeoFileResponse Pydantic schema
│   │   └── feature.py            # FeatureMeasurement, MeasurementsResponse Pydantic schemas
│   ├── services/
│   │   ├── parser.py             # Shapefile parser (Fiona) + KML parser (stdlib xml)
│   │   ├── crs.py                # CRS normalisation, UTM zone selection, reprojection
│   │   ├── measurement.py        # Area and length calculation on projected geometries
│   │   └── processor.py          # Orchestrates: parse → measure → persist
│   └── api/
│       └── routes/
│           └── files.py          # Route handlers for all /api/files/ endpoints
├── uploads/                      # Uploaded files stored here (git-ignored)
├── requirements.txt
├── .env.example
└── README.md
```

### File-processing flow

```
POST /api/files/
        │
        ▼
   Validate extension (.zip or .kml)
   Validate file size (max 50 MB)
        │
        ▼
   Save file to uploads/ with UUID prefix
        │
        ▼
   Create GeoFile record  →  status: PENDING
        │
        ▼
   processor.process_geo_file()
        │
        ├── status → PROCESSING
        │
        ├── parser.parse_shapefile()  or  parser.parse_kml()
        │       Shapefile: unzip to temp dir → Fiona reads .shp → extract features
        │       KML:       stdlib xml.etree → extract Placemarks → build Shapely geometries
        │       Returns: list of feature dicts + CRS string
        │
        ├── for each feature:
        │       ├── shapely.wkt.loads()  →  Shapely geometry object
        │       ├── measurement.calculate_measurements(geometry, crs)
        │       │       ├── crs.choose_projected_crs()   →  pick UTM zone or Equal Earth
        │       │       ├── crs.reproject_geometry()     →  pyproj transform to metres
        │       │       └── geometry.area  /  geometry.length
        │       └── persist GeoFeature row to SQLite
        │
        └── status → COMPLETED  (or FAILED on any unhandled exception)
```

### Measurement calculation flow

1. Receive a Shapely geometry and its source CRS string.
2. Check geometry type — Points get `null` immediately; unsupported types also get `null` with no crash.
3. Call `choose_projected_crs()` to get a metric CRS (see CRS Handling below).
4. Reproject the geometry using `pyproj.Transformer`.
5. Call `geometry.area` (Polygons) or `geometry.length` (LineStrings) on the projected geometry.
6. Return `(area_m2, length_m)`.

### CRS handling

The application **never** calculates area or length in geographic (lat/lon) degrees. All measurements are performed in a projected, metric coordinate system.

**Strategy (`app/services/crs.py → choose_projected_crs`):**

1. Parse the source CRS string using pyproj.
2. If the source CRS is already projected (e.g. EPSG:27700 British National Grid), use it directly — no reprojection needed.
3. If the source CRS is geographic (e.g. EPSG:4326), find the geometry's centroid and select the matching **UTM zone** (e.g. EPSG:32643 for Bangalore at ~77°E).
4. If the centroid is outside the valid UTM range (above 84°N or below 80°S), fall back to **EPSG:8857 (Equal Earth)**, a globally valid equal-area projection.
5. Reproject using `pyproj.Transformer.from_crs(..., always_xy=True)` to avoid axis-order issues.

**Example:** A KML file in EPSG:4326 with features near Bangalore (77°E, 13°N) will be reprojected to EPSG:32643 (WGS 84 / UTM Zone 43N) before measuring.

---

## Design Decisions

| Decision | Choice made | Alternatives considered |
|----------|-------------|------------------------|
| **Framework** | FastAPI | Django REST Framework. FastAPI was chosen for its automatic OpenAPI/Swagger docs, Pydantic v2 validation, and async-ready design. For a focused API service it has less boilerplate than Django. |
| **Database** | SQLAlchemy + SQLite | PostgreSQL + PostGIS. SQLite requires zero infrastructure for local development and setup. PostGIS would be the right choice in production for native spatial queries and indexing. |
| **Geospatial stack** | Fiona + Shapely + pyproj | GeoPandas (wraps the same stack but adds heavier pandas dependency), GDAL Python bindings (lower-level, more complex API). Fiona/Shapely/pyproj offers fine-grained control with a clean Python API. |
| **KML parsing** | Python stdlib `xml.etree` | Fiona with KML driver. The Fiona Windows PyPI wheel does not ship libkml, making KML support unreliable on Windows. The stdlib parser has zero extra dependencies and works on all platforms. |
| **CRS projection strategy** | UTM zone auto-selection + Equal Earth fallback | A single global projection (e.g. Web Mercator EPSG:3857). UTM gives the best local accuracy. Equal Earth (EPSG:8857) is an accurate global fallback. Web Mercator distorts area significantly away from the equator and was ruled out. |
| **Processing mode** | Synchronous (in-request) | Celery + Redis async task queue. Synchronous processing keeps the stack simple and dependency-free. For large files or high concurrency, moving to a background task queue would be the correct next step. |
| **File storage** | Local disk | S3-compatible object storage. Local disk is sufficient for local development. Cloud storage (boto3, S3 pre-signed URLs) would be needed for a production deployment. |
| **Geometry storage** | WKT string in SQLite TEXT column | GeoJSON, WKB. WKT is human-readable and does not require a PostGIS extension to store or inspect. |

---

## Learnings & Future Scope

### Learnings

- **pyproj axis order**: passing `always_xy=True` to `Transformer.from_crs` is essential. Without it, some CRS definitions use (latitude, longitude) axis order which silently swaps coordinates and produces wrong measurements.
- **Fiona KML driver**: the standard Fiona wheel on Windows does not include libkml. Detecting this early and using a stdlib fallback is the most portable approach.
- **UTM edge cases**: UTM zones are highly accurate locally but are undefined near the poles and produce distortion for geometries spanning more than one zone. Equal Earth (EPSG:8857) is a robust global fallback.
- **SQLAlchemy + SQLite thread safety**: SQLite requires `check_same_thread=False` when used with FastAPI's dependency injection because the session may be created on a different thread than it is used on.

### Future Scope

| Area | Improvement |
|------|-------------|
| Async processing | Move file processing into a Celery or ARQ background worker. The upload endpoint returns immediately with `status: PENDING` and the client polls `GET /api/files/{id}/` for completion. |
| Cloud storage | Replace local disk with S3-compatible object storage (boto3). Return pre-signed download URLs in the file response. |
| Production database | Migrate to PostgreSQL + PostGIS to enable native spatial queries, bounding-box filters, and spatial indexing. |
| Additional formats | Add support for GeoJSON (`.geojson`), GeoPackage (`.gpkg`), and CSV with WKT columns via existing Fiona drivers. |
| Pagination | Add `?page` and `?page_size` query parameters to `GET /api/files/{id}/measurements/` for files with thousands of features. |
| Authentication | Add API key or OAuth2 Bearer token authentication for multi-tenant or public deployments. |
| Containerisation | Add a `Dockerfile` and `docker-compose.yml` for a one-command local setup. |
| Automated tests | Add a pytest suite with fixture Shapefiles and KML files covering the full pipeline — upload, parse, measure, retrieve. |
