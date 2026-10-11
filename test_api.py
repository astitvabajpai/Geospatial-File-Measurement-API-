"""
End-to-end API test script.
Run with:  python test_api.py
Requires the server to be running: uvicorn app.main:app --reload
"""

import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8001"
KML_FILE = "test_sample.kml"

GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def section(msg): print(f"\n{BOLD}{CYAN}=== {msg} ==={RESET}")


# ── helpers ────────────────────────────────────────────────────────────────

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())


def post_file(path, filepath):
    import uuid, mimetypes
    boundary = uuid.uuid4().hex
    with open(filepath, "rb") as f:
        file_data = f.read()
    filename = filepath.split("/")[-1].split("\\")[-1]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ── tests ──────────────────────────────────────────────────────────────────

def test_health():
    section("1. Health Check  GET /")
    status, body = get("/")
    assert status == 200, f"Expected 200, got {status}"
    assert body["status"] == "ok"
    ok(f"Status 200 — {body['message']}")


def test_upload(kml_path):
    section("2. Upload File  POST /api/files/")
    status, body = post_file("/api/files/", kml_path)
    print(f"  Response: {json.dumps(body, indent=4)}")
    assert status == 201, f"Expected 201, got {status}\n{body}"
    assert body["status"] == "COMPLETED", f"Expected COMPLETED, got {body['status']}"
    assert body["feature_count"] == 3, f"Expected 3 features, got {body['feature_count']}"
    ok(f"Upload succeeded — file id: {body['id']}")
    ok(f"CRS detected: {body['crs']}")
    ok(f"Features found: {body['feature_count']}")
    return body["id"]


def test_get_file(file_id):
    section("3. Get File Info  GET /api/files/{id}/")
    status, body = get(f"/api/files/{file_id}/")
    print(f"  Response: {json.dumps(body, indent=4)}")
    assert status == 200
    assert body["id"] == file_id
    assert body["status"] == "COMPLETED"
    ok("File metadata returned correctly")


def test_measurements(file_id):
    section("4. Get Measurements  GET /api/files/{id}/measurements/")
    status, body = get(f"/api/files/{file_id}/measurements/")
    print(f"  Response: {json.dumps(body, indent=4)}")
    assert status == 200
    assert body["feature_count"] == 3

    features = body["features"]
    polygon   = next(f for f in features if f["geometry_type"] == "Polygon")
    linestr   = next(f for f in features if f["geometry_type"] == "LineString")
    point     = next(f for f in features if f["geometry_type"] == "Point")

    # Polygon — should have area, no length
    assert polygon["area_m2"] is not None and polygon["area_m2"] > 0, "Polygon should have area"
    assert polygon["length_m"] is None, "Polygon should not have length"
    ok(f"Polygon area: {polygon['area_m2']:,.2f} m²  ({polygon['area_m2']/1_000_000:.4f} km²)")

    # LineString — should have length, no area
    assert linestr["length_m"] is not None and linestr["length_m"] > 0, "LineString should have length"
    assert linestr["area_m2"] is None, "LineString should not have area"
    ok(f"LineString length: {linestr['length_m']:,.2f} m  ({linestr['length_m']/1000:.4f} km)")

    # Point — no measurement at all
    assert point["area_m2"] is None, "Point should not have area"
    assert point["length_m"] is None, "Point should not have length"
    ok("Point correctly has no measurements (null)")


def test_not_found():
    section("5. 404 on unknown file  GET /api/files/doesnotexist/")
    try:
        status, body = get("/api/files/doesnotexist/")
        assert status == 404, f"Expected 404, got {status}"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        body = json.loads(e.read())
    ok(f"Got 404 as expected — {body['detail']}")


def test_bad_upload():
    section("6. Reject unsupported file type  POST /api/files/ (.txt)")
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.write(b"not a geo file")
    tmp.close()
    try:
        status, body = post_file("/api/files/", tmp.name)
        assert status == 415, f"Expected 415, got {status}"
        ok(f"Got 415 Unsupported Media Type — {body['detail']}")
    finally:
        os.unlink(tmp.name)


# ── run all ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{BOLD}Geospatial API — End-to-End Tests{RESET}")
    print(f"Target: {BASE_URL}\n")

    passed = failed = 0
    results = []

    def run(fn, *args):
        global passed, failed
        try:
            fn(*args)
            passed += 1
            results.append((fn.__name__, True, None))
        except Exception as e:
            failed += 1
            results.append((fn.__name__, False, str(e)))
            fail(f"FAILED: {e}")

    test_health()
    file_id = None

    try:
        _, upload_body = post_file("/api/files/", KML_FILE)
        file_id = upload_body.get("id")
    except Exception as e:
        fail(f"Could not upload — aborting dependent tests: {e}")

    run(test_health)
    run(test_upload, KML_FILE)
    if file_id:
        run(test_get_file, file_id)
        run(test_measurements, file_id)
    run(test_not_found)
    run(test_bad_upload)

    section("Summary")
    print(f"  {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}\n")
