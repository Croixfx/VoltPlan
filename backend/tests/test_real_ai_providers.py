import asyncio
import io
import json

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import vision_service
from app.services.vision_service import (
    GeminiVisionProvider,
    MockVisionProvider,
    OpenAIVisionProvider,
    VisionProviderError,
    describe_http_error,
    redact,
)

KEY = "AIzaSyFAKE-secret-key-123456"
REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def plan_png(tmp_path):
    path = tmp_path / "plan.png"
    Image.new("RGB", (400, 300), (255, 255, 255)).save(path)
    return str(path)


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", KEY)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test-model")


@pytest.fixture
def network(monkeypatch):
    """Route every httpx.AsyncClient through `handler`; returns the list of requests it saw."""
    seen = []

    def install(handler):
        def wrapped(request):
            seen.append(request)
            return handler(request)

        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda *a, **kw: REAL_ASYNC_CLIENT(*a, transport=httpx.MockTransport(wrapped), **kw),
        )
        return seen

    return install


# What a model returns for the plan: the mock provider's rooms and doors, serialised. Computed once, outside any
# running event loop, because the fake network handlers below run inside one.
_PLAN_ANSWER = asyncio.run(
    MockVisionProvider().analyze_floor_plan("x.png", "Residential", "RS IEC 60364")
).model_dump()


def plan_answer() -> dict:
    return json.loads(json.dumps(_PLAN_ANSWER))


def gemini_ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


def analyze(provider, path):
    return asyncio.run(provider.analyze_floor_plan(path, "Residential", "RS IEC 60364"))


# ----------------------------------------------------------------------------- Gemini
def test_gemini_reads_the_answer_and_keeps_the_key_out_of_the_url(gemini, network, plan_png):
    seen = network(lambda req: gemini_ok(plan_answer()))
    result = analyze(GeminiVisionProvider(), plan_png)

    assert len(result.rooms) == 6 and any(f.type == "door" for f in result.architectural_features)
    req = seen[0]
    assert req.headers["x-goog-api-key"] == KEY
    assert KEY not in str(req.url) and "key=" not in str(req.url)
    assert str(req.url).endswith("/v1beta/models/gemini-test-model:generateContent")
    body = json.loads(req.content)
    assert body["generationConfig"]["response_mime_type"] == "application/json"
    assert body["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"


def test_model_names_may_include_the_models_prefix(gemini, network, plan_png, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_MODEL", "models/gemini-test-model")
    seen = network(lambda req: gemini_ok(plan_answer()))
    analyze(GeminiVisionProvider(), plan_png)
    assert "/models/gemini-test-model:generateContent" in str(seen[0].url) and "models/models" not in str(seen[0].url)


def test_gemini_http_errors_say_what_google_said_and_never_leak_the_key(gemini, network, plan_png):
    network(lambda req: httpx.Response(404, json={"error": {"code": 404, "message": "models/gemini-test-model is not found"}}))
    with pytest.raises(VisionProviderError) as exc:
        analyze(GeminiVisionProvider(), plan_png)
    msg = str(exc.value)
    assert "HTTP 404" in msg and "is not found" in msg and "/api/ai/check" in msg
    assert KEY not in msg and "key=" not in msg


def test_exceptions_that_contain_the_key_are_redacted(gemini, network, plan_png):
    def boom(req):
        raise httpx.ConnectError(f"connection failed for https://generativelanguage.googleapis.com/x?key={KEY}")

    network(boom)
    with pytest.raises(VisionProviderError) as exc:
        analyze(GeminiVisionProvider(), plan_png)
    assert KEY not in str(exc.value) and "***" in str(exc.value)


def test_unusable_answers_get_clear_messages(gemini, network, plan_png):
    cases = {
        "valid JSON": httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Sure! Here are the rooms..."}]}}]}),
        "did not match the expected room/door format": gemini_ok({"rooms": [{"id": 1}]}),
        "SAFETY": httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
    }
    for fragment, response in cases.items():
        network(lambda req, r=response: r)
        with pytest.raises(VisionProviderError) as exc:
            analyze(GeminiVisionProvider(), plan_png)
        assert fragment in str(exc.value), fragment
        assert KEY not in str(exc.value)


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(vision_service.asyncio, "sleep", fake_sleep)
    return slept


def test_temporary_provider_errors_are_retried(gemini, network, no_sleep, plan_png):
    answers = iter([
        httpx.Response(503, json={"error": {"message": "This model is currently experiencing high demand."}}),
        httpx.Response(429, json={"error": {"message": "Resource exhausted"}}),
        gemini_ok(plan_answer()),
    ])
    seen = network(lambda req: next(answers))
    assert len(analyze(GeminiVisionProvider(), plan_png).rooms) == 6
    assert len(seen) == 3 and no_sleep == [2.0, 5.0]


def test_retries_give_up_and_report_the_last_error(gemini, network, no_sleep, plan_png):
    seen = network(lambda req: httpx.Response(503, json={"error": {"message": "high demand"}}))
    with pytest.raises(VisionProviderError) as exc:
        analyze(GeminiVisionProvider(), plan_png)
    assert len(seen) == 3 and "HTTP 503: high demand" in str(exc.value) and KEY not in str(exc.value)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_mistakes_in_the_request_are_not_retried(gemini, network, no_sleep, plan_png, status):
    seen = network(lambda req: httpx.Response(status, json={"error": {"message": "nope"}}))
    with pytest.raises(VisionProviderError):
        analyze(GeminiVisionProvider(), plan_png)
    assert len(seen) == 1 and no_sleep == []


def test_openai_temporary_errors_are_retried_too(monkeypatch, network, no_sleep, plan_png):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-secret-abcdef123456")
    answers = iter([httpx.Response(500), httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan_answer())}}]})])
    seen = network(lambda req: next(answers))
    assert len(analyze(OpenAIVisionProvider(), plan_png).rooms) == 6 and len(seen) == 2


def test_a_missing_key_is_reported_not_replaced_by_mock_data(monkeypatch, plan_png):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(VisionProviderError, match="GEMINI_API_KEY"):
        analyze(GeminiVisionProvider(), plan_png)


# ----------------------------------------------------------------------------- OpenAI
def test_openai_errors_are_explained_and_redacted(monkeypatch, network, plan_png):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-secret-abcdef123456")
    network(lambda req: httpx.Response(401, json={"error": {"message": "Incorrect API key provided: sk-secret-abcdef123456"}}))
    with pytest.raises(VisionProviderError) as exc:
        analyze(OpenAIVisionProvider(), plan_png)
    assert "HTTP 401" in str(exc.value) and "sk-secret-abcdef123456" not in str(exc.value)


def test_openai_success(monkeypatch, network, plan_png):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-secret-abcdef123456")
    seen = network(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan_answer())}}]}))
    assert len(analyze(OpenAIVisionProvider(), plan_png).rooms) == 6
    assert seen[0].headers["authorization"] == "Bearer sk-secret-abcdef123456"


# ----------------------------------------------------------------------------- helpers
def test_redact_and_describe_http_error():
    assert redact("GET https://x/y?key=SECRET&alt=json failed", "other") == "GET https://x/y?key=***&alt=json failed"
    assert redact("token abcd1234 leaked", "abcd1234") == "token *** leaked"
    assert redact("short", "ab") == "short"                      # too short to be a secret: left alone
    assert describe_http_error(httpx.Response(429, json={"error": {"message": "Quota exceeded"}})) == "HTTP 429: Quota exceeded"
    assert describe_http_error(httpx.Response(502, text="Bad gateway")) == "HTTP 502: Bad gateway"
    assert describe_http_error(httpx.Response(500)) == "HTTP 500"


# ----------------------------------------------------------------------------- through the API
def _project_with_plan(client):
    pid = client.post("/api/projects", json={"name": "Real AI", "client": "Client", "location": "Kigali"}).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (255, 255, 255)).save(buf, format="PNG")
    buf.seek(0)
    client.post(f"/api/projects/{pid}/plan", files={"file": ("p.png", buf, "image/png")})
    return pid


def test_analysis_with_gemini_end_to_end(client, gemini, network):
    network(lambda req: gemini_ok(plan_answer()) if req.method == "POST" else httpx.Response(404))
    pid = _project_with_plan(client)
    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed" and len(body["electrical_points"]) > 0
    assert not any("DEMO DATA" in w for w in body["warnings"])        # real provider: no demo-data warning


def test_a_gemini_failure_reaches_the_user_without_the_key(client, gemini, network):
    network(lambda req: httpx.Response(403, json={"error": {"message": f"API key not valid ({KEY[:6]}...)"}}))
    pid = _project_with_plan(client)
    res = client.post(f"/api/projects/{pid}/analyze")
    assert res.status_code == 502
    assert "HTTP 403" in res.json()["detail"] and KEY not in res.text
    status = client.get(f"/api/projects/{pid}/analysis/status").json()
    assert status["status"] == "failed" and KEY not in json.dumps(status)


# ----------------------------------------------------------------------------- /api/ai/check
MODELS = {"models": [
    {"name": "models/gemini-test-model", "supportedGenerationMethods": ["generateContent", "countTokens"]},
    {"name": "models/gemini-other-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
]}


def test_ai_check_reports_an_available_model(client, gemini, network):
    seen = network(lambda req: httpx.Response(200, json=MODELS))
    body = client.get("/api/ai/check").json()
    assert body["ok"] is True and body["model_available"] is True
    assert body["available_models"] == ["gemini-other-flash", "gemini-test-model"]      # embeddings are not listed
    assert seen[0].headers["x-goog-api-key"] == KEY and KEY not in client.get("/api/ai/check").text


def test_ai_check_suggests_models_when_the_configured_one_is_unavailable(client, gemini, network, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-retired")
    network(lambda req: httpx.Response(200, json=MODELS))
    body = client.get("/api/ai/check").json()
    assert body["ok"] is True and body["model_available"] is False
    assert "gemini-retired" in body["message"] and "gemini-test-model" in body["available_models"]


def test_ai_check_explains_a_rejected_key(client, gemini, network):
    network(lambda req: httpx.Response(400, json={"error": {"message": "API key not valid. Please pass a valid API key."}}))
    body = client.get("/api/ai/check").json()
    assert body["ok"] is False and "HTTP 400" in body["message"] and "copied completely" in body["message"]
    assert KEY not in json.dumps(body)


def test_ai_check_other_states(client, monkeypatch, network):
    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    assert client.get("/api/ai/check").json()["ok"] is True

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert "not set" in client.get("/api/ai/check").json()["message"]

    monkeypatch.setattr(settings, "AI_PROVIDER", "bogus")
    assert "Unknown AI_PROVIDER" in client.get("/api/ai/check").json()["message"]

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-secret-abcdef123456")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o")
    network(lambda req: httpx.Response(200, json={"data": [{"id": "gpt-4o"}, {"id": "whisper-1"}]}))
    body = client.get("/api/ai/check").json()
    assert body["ok"] and body["model_available"] and body["available_models"] == ["gpt-4o"]


def test_ai_check_needs_the_api_key_like_every_other_route(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "gate")
    assert client.get("/api/ai/check").status_code == 401
    assert client.get("/api/ai/check", headers={"X-API-Key": "gate"}).status_code == 200
