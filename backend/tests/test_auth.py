import io

import pytest
from PIL import Image

from app.api.routes import auth as auth_routes
from app.core import auth
from app.core.config import settings
from app.models.project import Project
from app.models.user import User

PROJECT = {"name": "Auth test", "client": "Some Client", "building_type": "Residential", "location": "Kigali",
           "standard": "RS IEC 60364", "notes": ""}


@pytest.fixture(autouse=True)
def login_on(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "test-secret-test-secret-test-secret")
    monkeypatch.setattr(settings, "LEGACY_OWNER_EMAIL", "")
    auth_routes._failures.clear()


def register(client, email="ana@example.com", password="correct horse", name="Ana"):
    res = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def png():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_nothing_is_reachable_without_signing_in(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json=PROJECT).status_code == 401
    assert client.get("/api/equipment").status_code == 401
    assert client.get("/api/projects", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get("/api/health").status_code == 200  # the platform's health probe stays public


def test_register_then_sign_in(client):
    headers = register(client)
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "ana@example.com"

    ok = client.post("/api/auth/login", json={"email": " ANA@example.com ", "password": "correct horse"})
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "Ana"
    bad = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert unknown.status_code == 401 and unknown.json()["detail"] == bad.json()["detail"]


def test_registration_is_checked(client):
    assert client.post("/api/auth/register", json={"email": "not-an-email", "password": "long enough"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    register(client)
    assert client.post("/api/auth/register",
                       json={"email": "ANA@example.com", "password": "another one"}).status_code == 409


def test_passwords_are_stored_hashed(client, db_session):
    register(client)
    stored = db_session.query(User).one().password_hash
    assert "correct horse" not in stored and stored.startswith("pbkdf2_sha256$")


def test_a_user_sees_and_touches_only_their_own_projects(client):
    ana = register(client, "ana@example.com")
    ben = register(client, "ben@example.com", name="Ben")

    pid = client.post("/api/projects", json=PROJECT, headers=ana).json()["id"]
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", png(), "image/png")}, headers=ana)
    assert client.post(f"/api/projects/{pid}/analyze", headers=ana).status_code == 200

    assert [p["id"] for p in client.get("/api/projects", headers=ana).json()] == [pid]
    assert client.get("/api/projects", headers=ben).json() == []

    # every kind of route under /projects/{id} answers 404 for someone else, exactly as for a missing project
    for method, path in [
        ("get", f"/api/projects/{pid}"),
        ("get", f"/api/projects/{pid}/analysis"),
        ("get", f"/api/projects/{pid}/plan/file"),
        ("get", f"/api/projects/{pid}/report.pdf"),
        ("get", f"/api/projects/{pid}/calculations"),
        ("get", f"/api/projects/{pid}/scale"),
        ("post", f"/api/projects/{pid}/analyze"),
        ("post", f"/api/projects/{pid}/scale/suggest"),
        ("patch", f"/api/projects/{pid}"),
        ("delete", f"/api/projects/{pid}"),
    ]:
        res = getattr(client, method)(path, headers=ben)
        assert res.status_code == 404, f"{method} {path} -> {res.status_code}"
        assert res.json()["detail"] == "Project not found."

    # the owner still can, and Ben's attempts changed nothing
    assert client.get(f"/api/projects/{pid}/report.pdf", headers=ana).status_code == 200
    assert client.get(f"/api/projects/{pid}", headers=ana).status_code == 200


def test_duplicate_plan_lookup_never_reveals_another_users_project(client):
    ana = register(client, "ana@example.com")
    ben = register(client, "ben@example.com", name="Ben")
    pid = client.post("/api/projects", json=PROJECT, headers=ana).json()["id"]
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", png(), "image/png")}, headers=ana)

    mine = client.post("/api/projects/plan-match", files={"file": ("p.png", png(), "image/png")}, headers=ana)
    assert mine.status_code == 200 and mine.json()["id"] == pid
    theirs = client.post("/api/projects/plan-match", files={"file": ("p.png", png(), "image/png")}, headers=ben)
    assert theirs.status_code == 200 and theirs.json() is None


def test_tokens_cannot_be_forged_or_reused_after_expiry(client, db_session):
    register(client)
    user = db_session.query(User).one()

    token = auth.create_token(user)
    assert auth.read_token(token) == user.id
    version, body, signature = token.split(".")
    assert auth.read_token(f"{version}.{body}.{signature[:-2]}AA") is None   # altered signature
    assert auth.read_token(f"{version}.{body}x.{signature}") is None         # altered payload
    assert auth.read_token("garbage") is None
    assert auth.read_token(token, now=1e12) is None                           # expired

    # a token signed with another secret is worthless
    settings.AUTH_SECRET = "a-completely-different-secret-value"
    assert auth.read_token(token) is None


def test_a_token_for_a_deleted_user_stops_working(client, db_session):
    headers = register(client)
    db_session.delete(db_session.query(User).one())
    db_session.commit()
    assert client.get("/api/projects", headers=headers).status_code == 401


def test_guessing_a_password_is_throttled(client):
    register(client)
    for _ in range(auth_routes.MAX_FAILURES):
        assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "correct horse"})
    assert locked.status_code == 429


def test_projects_made_before_accounts_go_to_the_configured_owner(client, db_session, monkeypatch):
    db_session.add(Project(name="Old project", client="Old Client", location="Kigali", building_type="Residential"))
    db_session.commit()
    monkeypatch.setattr(settings, "LEGACY_OWNER_EMAIL", "boss@example.com")

    other = register(client, "ana@example.com")
    assert client.get("/api/projects", headers=other).json() == []   # not the owner: sees nothing

    boss = register(client, "boss@example.com", name="Boss")
    assert [p["name"] for p in client.get("/api/projects", headers=boss).json()] == ["Old project"]


def test_login_is_off_without_a_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "")
    assert client.get("/api/projects").status_code == 200       # local development works as before
    assert client.post("/api/projects", json=PROJECT).status_code == 201
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "long enough"}).status_code == 503
