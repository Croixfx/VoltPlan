import io
from PIL import Image


def _create_test_png():
    img = Image.new("RGB", (400, 300), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def test_upload_valid_floor_plan_image(client):
    proj_res = client.post(
        "/api/projects",
        json={
            "name": "Floor Plan Upload Test",
            "client": "Test Client",
            "building_type": "Residential",
            "location": "Kigali",
            "standard": "RS IEC 60364",
        },
    )
    proj_id = proj_res.json()["id"]

    png_bytes = _create_test_png()
    files = {"file": ("villa_plan.png", png_bytes, "image/png")}

    upload_res = client.post(f"/api/projects/{proj_id}/plan", files=files)
    assert upload_res.status_code == 200
    updated = upload_res.json()
    assert updated["status"] == "uploaded"
    assert updated["floor_plan_name"] == "villa_plan.png"
    assert updated["floor_plan_size"] > 0

    # Stream the plan image
    file_res = client.get(f"/api/projects/{proj_id}/plan/file")
    assert file_res.status_code == 200
    assert file_res.headers["content-type"] == "image/png"


def test_upload_unsupported_extension(client):
    proj_res = client.post(
        "/api/projects",
        json={
            "name": "Invalid File Test",
            "client": "Client",
            "building_type": "Residential",
            "location": "Kigali",
            "standard": "RS IEC 60364",
        },
    )
    proj_id = proj_res.json()["id"]

    files = {"file": ("drawing.dwg", b"fake dwg content", "application/octet-stream")}
    upload_res = client.post(f"/api/projects/{proj_id}/plan", files=files)
    assert upload_res.status_code == 400
    assert "Unsupported file format" in upload_res.json()["detail"]


def test_upload_empty_file(client):
    proj_res = client.post(
        "/api/projects",
        json={
            "name": "Empty File Test",
            "client": "Client",
            "building_type": "Residential",
            "location": "Kigali",
            "standard": "RS IEC 60364",
        },
    )
    proj_id = proj_res.json()["id"]

    files = {"file": ("empty.png", b"", "image/png")}
    upload_res = client.post(f"/api/projects/{proj_id}/plan", files=files)
    assert upload_res.status_code == 400
    assert "empty" in upload_res.json()["detail"].lower()
