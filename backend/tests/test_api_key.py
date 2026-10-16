import io

import pytest
from PIL import Image

from app.core.config import Settings, settings
from app.core.security import check_deployment_safety
from app.db.database import normalize_database_url

KEY = "test-key-0123456789"


@pytest.fixture
def locked(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", KEY)
    return {"X-API-Key": KEY}


def test_everything_is_open_when_no_key_is_configured(client):
    # local development and the rest of the test-suite rely on this
    assert settings.API_KEY == ""
    assert client.get("/api/equipment").status_code == 200
    assert client.get("/api/projects").status_code == 200


def test_requests_without_or_with_a_wrong_key_are_rejected(client, locked):
    for headers in ({}, {"X-API-Key": "wrong"}, {"X-API-Key": KEY[:-1]}, {"X-API-Key": KEY + "x"}, {"X-API-Key": ""}):
        res = client.get("/api/projects", headers=headers)
        assert res.status_code == 401, headers
        assert res.json()["detail"] == "Invalid or missing API key."
        assert res.headers["www-authenticate"] == "ApiKey"


def test_the_right_key_gets_through(client, locked):
    assert client.get("/api/projects", headers=locked).status_code == 200
    assert client.get("/api/equipment", headers=locked).status_code == 200


def test_health_stays_public_for_platform_probes(client, locked):
    res = client.get("/api/health")
    assert res.status_code == 200 and res.json()["status"] == "ok"


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/api/projects", {"name": "Abuse", "client": "Client", "location": "Kigali"}),
        ("get", "/api/projects/x", None),
        ("delete", "/api/projects/x", None),
        ("post", "/api/projects/x/analyze", None),
        ("get", "/api/projects/x/geometry", None),
        ("post", "/api/projects/x/regenerate", None),
        ("post", "/api/projects/x/points", {"type": "twin_socket", "x_ratio": 0.5, "y_ratio": 0.5}),
        ("get", "/api/projects/x/calculations", None),
        ("put", "/api/projects/x/scale", {"point_a": {"x_ratio": 0.1, "y_ratio": 0.1},
                                          "point_b": {"x_ratio": 0.5, "y_ratio": 0.1}, "real_distance_mm": 1000}),
        ("get", "/api/projects/x/plan/file", None),
        ("get", "/api/projects/x/boq", None),
    ],
)
def test_every_data_route_is_protected(client, locked, method, path, body):
    res = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert res.status_code == 401, f"{method.upper()} {path} was reachable without the key"
    # ... and with the key the route is reachable (it may then 404/422 on the dummy id, but not 401)
    with_key = getattr(client, method)(path, headers=locked, **({"json": body} if body is not None else {}))
    assert with_key.status_code != 401


def test_uploads_and_plan_downloads_need_the_key(client, locked):
    pid = client.post("/api/projects", headers=locked, json={"name": "Locked", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (100, 80), (255, 255, 255)).save(buf, format="PNG")
    files = {"file": ("p.png", buf.getvalue(), "image/png")}

    assert client.post(f"/api/projects/{pid}/plan", files=files).status_code == 401
    assert client.post(f"/api/projects/{pid}/plan", files=files, headers=locked).status_code == 200
    assert client.get(f"/api/projects/{pid}/plan/file").status_code == 401
    assert client.get(f"/api/projects/{pid}/plan/file", headers=locked).status_code == 200


# --------------------------------------------------------------------------- deployment guards
def cfg(**kw):
    return Settings(_env_file=None, **kw)


def test_production_with_a_real_ai_provider_refuses_to_start_without_a_key():
    for provider in ("gemini", "openai", "GEMINI"):
        with pytest.raises(RuntimeError, match="API_KEY"):
            check_deployment_safety(cfg(APP_ENV="production", AI_PROVIDER=provider, API_KEY=""))


def test_other_combinations_are_allowed():
    check_deployment_safety(cfg(APP_ENV="production", AI_PROVIDER="gemini", API_KEY="k", AUTH_SECRET="s"))  # protected
    check_deployment_safety(cfg(APP_ENV="production", AI_PROVIDER="mock", API_KEY="", AUTH_SECRET="s"))     # nothing to spend
    check_deployment_safety(cfg(APP_ENV="development", AI_PROVIDER="gemini", API_KEY=""))     # local use


def test_production_refuses_to_start_without_a_login_secret():
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        check_deployment_safety(cfg(APP_ENV="production", AI_PROVIDER="mock", API_KEY="k", AUTH_SECRET=""))


def test_postgres_urls_from_hosting_platforms_are_normalised():
    # always the driver listed in requirements.txt, whatever SQLAlchemy's default happens to be
    assert normalize_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg2://u:p@h:5432/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_database_url("postgresql+psycopg2://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_database_url("sqlite:///./voltplan.db") == "sqlite:///./voltplan.db"
