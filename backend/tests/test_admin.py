import io

import pytest
from PIL import Image

from app.api.routes import auth as auth_routes
from app.core.config import settings

PROJECT = {"name": "Admin test", "client": "Some Client", "building_type": "Residential", "location": "Kigali",
           "standard": "RS IEC 60364", "notes": ""}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "test-secret-test-secret-test-secret")
    monkeypatch.setattr(settings, "LEGACY_OWNER_EMAIL", "")
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "Boss@Example.com, other@example.com")
    auth_routes._failures.clear()


def register(client, email, name=""):
    res = client.post("/api/auth/register", json={"email": email, "password": "long enough pw", "name": name})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, res.json()["user"]


def png():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_admin_flag_comes_from_the_configured_emails(client):
    _, boss = register(client, "boss@example.com")
    _, ana = register(client, "ana@example.com")
    assert boss["is_admin"] is True
    assert ana["is_admin"] is False


def test_normal_users_cannot_reach_admin_routes(client):
    ana, _ = register(client, "ana@example.com")
    for path in ("/api/admin/overview", "/api/admin/users", "/api/admin/projects"):
        assert client.get(path, headers=ana).status_code == 403
    assert client.get("/api/admin/users").status_code == 401


def test_admin_sees_every_account_and_project(client):
    boss, _ = register(client, "boss@example.com")
    ana, _ = register(client, "ana@example.com", "Ana")
    ben, _ = register(client, "ben@example.com", "Ben")
    client.post("/api/projects", json={**PROJECT, "name": "Ana villa"}, headers=ana)
    client.post("/api/projects", json={**PROJECT, "name": "Ben shop"}, headers=ben)

    overview = client.get("/api/admin/overview", headers=boss).json()
    assert overview["users"] == 3 and overview["projects"] == 2

    users = {u["email"]: u for u in client.get("/api/admin/users", headers=boss).json()}
    assert users["ana@example.com"]["project_count"] == 1
    assert users["boss@example.com"]["is_admin"] is True

    projects = client.get("/api/admin/projects", headers=boss).json()
    assert {(p["name"], p["owner_email"]) for p in projects} == {
        ("Ana villa", "ana@example.com"), ("Ben shop", "ben@example.com")}
    found = client.get("/api/admin/projects?q=ben@", headers=boss).json()
    assert [p["name"] for p in found] == ["Ben shop"]

    # the admin's own dashboard list still shows only their own projects
    assert client.get("/api/projects", headers=boss).json() == []


def test_admin_can_open_any_project_and_its_report(client):
    boss, _ = register(client, "boss@example.com")
    ana, _ = register(client, "ana@example.com")
    pid = client.post("/api/projects", json=PROJECT, headers=ana).json()["id"]
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", png(), "image/png")}, headers=ana)
    assert client.post(f"/api/projects/{pid}/analyze", headers=ana).status_code == 200

    assert client.get(f"/api/projects/{pid}", headers=boss).status_code == 200
    assert client.get(f"/api/projects/{pid}/analysis", headers=boss).status_code == 200
    assert client.get(f"/api/projects/{pid}/report.pdf", headers=boss).status_code == 200
    # a missing project is still a 404 for the admin
    assert client.get("/api/projects/nope", headers=boss).status_code == 404


def test_deactivated_accounts_are_cut_off_and_can_return(client):
    boss, _ = register(client, "boss@example.com")
    ana, ana_user = register(client, "ana@example.com")
    assert client.get("/api/projects", headers=ana).status_code == 200

    off = client.post(f"/api/admin/users/{ana_user['id']}/deactivate", json={"reason": "spam"}, headers=boss)
    assert off.status_code == 200
    blocked = client.get("/api/projects", headers=ana)
    assert blocked.status_code == 403 and "deactivated" in blocked.json()["detail"]
    login = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "long enough pw"})
    assert login.status_code == 403

    listed = {u["email"]: u for u in client.get("/api/admin/users", headers=boss).json()}
    assert listed["ana@example.com"]["deactivated_reason"] == "spam"

    assert client.post(f"/api/admin/users/{ana_user['id']}/reactivate", headers=boss).status_code == 200
    assert client.get("/api/projects", headers=ana).status_code == 200


def test_admins_cannot_be_deactivated_and_unknown_accounts_404(client):
    boss, boss_user = register(client, "boss@example.com")
    assert client.post(f"/api/admin/users/{boss_user['id']}/deactivate", json={}, headers=boss).status_code == 400
    assert client.post("/api/admin/users/nope/deactivate", json={}, headers=boss).status_code == 404
