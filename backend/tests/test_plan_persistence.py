"""Uploaded drawings must survive the disk being wiped (free hosting restarts and sleeps)."""
import io
import os
import shutil

from PIL import Image

from app.models.plan_file import PlanFile


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), "white").save(buf, format="PNG")
    return buf.getvalue()


def _new_project(client, name: str) -> str:
    res = client.post("/api/projects", json={"name": name, "client": "Client", "location": "Kigali"})
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _project_with_plan(client) -> str:
    pid = _new_project(client, "Persist")
    r = client.post(f"/api/projects/{pid}/plan", files={"file": ("plan.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    return pid


def _wipe_disk(db_session, pid):
    from app.models.project import Project
    path = db_session.get(Project, pid).floor_plan_path
    shutil.rmtree(os.path.dirname(path))
    assert not os.path.exists(path)
    return path


def test_upload_keeps_a_copy_in_the_database(client, db_session):
    pid = _project_with_plan(client)
    row = db_session.get(PlanFile, pid)
    assert row is not None and row.original_bytes and row.display_png_bytes


def test_plan_is_served_again_after_the_disk_is_wiped(client, db_session):
    pid = _project_with_plan(client)
    path = _wipe_disk(db_session, pid)

    r = client.get(f"/api/projects/{pid}/plan/file")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert os.path.exists(path)  # rebuilt where everything else expects it


def test_original_is_served_after_the_disk_is_wiped(client, db_session):
    pid = _project_with_plan(client)
    _wipe_disk(db_session, pid)
    r = client.get(f"/api/projects/{pid}/plan/file", params={"format": "original"})
    assert r.status_code == 200 and r.content == _png()


def test_analysis_and_scale_work_after_the_disk_is_wiped(client, db_session):
    pid = _project_with_plan(client)
    _wipe_disk(db_session, pid)

    scale = client.put(f"/api/projects/{pid}/scale", json={
        "point_a": {"x_ratio": 0.1, "y_ratio": 0.5}, "point_b": {"x_ratio": 0.6, "y_ratio": 0.5},
        "real_distance_mm": 5000,
    })
    assert scale.status_code == 200, scale.text

    _wipe_disk(db_session, pid)
    analysis = client.post(f"/api/projects/{pid}/analyze")
    assert "No architectural floor plan" not in analysis.text
    assert "missing" not in analysis.text


def test_a_project_without_any_plan_still_reports_none(client):
    pid = _new_project(client, "Empty")
    assert client.get(f"/api/projects/{pid}/plan/file").status_code == 404


def test_deleting_a_project_removes_its_stored_plan(client, db_session):
    pid = _project_with_plan(client)
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    db_session.expire_all()
    assert db_session.get(PlanFile, pid) is None


def test_a_new_upload_replaces_the_stored_copy(client, db_session):
    pid = _project_with_plan(client)
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "black").save(buf, format="PNG")
    client.post(f"/api/projects/{pid}/plan", files={"file": ("second.png", buf.getvalue(), "image/png")})
    db_session.expire_all()
    assert db_session.get(PlanFile, pid).original_bytes == buf.getvalue()
