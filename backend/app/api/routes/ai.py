from typing import Any, Dict, List

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.services.vision_service import describe_http_error, gemini_model_path, redact

router = APIRouter(prefix="/ai", tags=["AI"])

_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


def _result(provider: str, model: str, **extra: Any) -> Dict[str, Any]:
    return {"provider": provider, "model": model, "ok": False, "model_available": None,
            "available_models": [], "message": "", **extra}


@router.get("/check")
async def check_ai() -> Dict[str, Any]:
    """Tests the configured AI provider without analysing a plan: is the key accepted and is the configured
    model available to it? Uses the key stored on the server; the key itself is never returned."""
    provider = settings.AI_PROVIDER.strip().lower()

    if provider == "mock":
        return _result("mock", "-", ok=True,
                       message="The mock provider returns the same demo rooms for every plan; no AI service is called. "
                               "Set AI_PROVIDER=gemini (or openai) and its API key to read real plans.")

    if provider == "gemini":
        model, key = settings.GEMINI_MODEL, settings.GEMINI_API_KEY
        if not key:
            return _result("gemini", model, message="GEMINI_API_KEY is not set.")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(_GEMINI_MODELS_URL, headers={"x-goog-api-key": key})
        except Exception as e:
            return _result("gemini", model, message=f"Could not reach Google: {redact(str(e), key)}")
        if resp.status_code >= 400:
            hint = " The key was rejected: check that it was copied completely." if resp.status_code in (400, 401, 403) else ""
            return _result("gemini", model, message=f"Google answered {describe_http_error(resp, key)}.{hint}")
        names: List[str] = []
        usable: List[str] = []
        for m in resp.json().get("models", []):
            names.append(m.get("name", ""))
            if "generateContent" in (m.get("supportedGenerationMethods") or []) and "gemini" in m.get("name", ""):
                usable.append(m["name"].removeprefix("models/"))
        available = gemini_model_path(model) in names
        return _result(
            "gemini", model, ok=True, model_available=available, available_models=sorted(usable),
            message=("Key accepted and the model is available." if available else
                     f"Key accepted, but the model '{model}' is not available to it. Set GEMINI_MODEL to one of "
                     "available_models (a recent 'flash' model is a good start)."),
        )

    if provider == "openai":
        model, key = settings.OPENAI_MODEL, settings.OPENAI_API_KEY
        if not key:
            return _result("openai", model, message="OPENAI_API_KEY is not set.")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(_OPENAI_MODELS_URL, headers={"Authorization": f"Bearer {key}"})
        except Exception as e:
            return _result("openai", model, message=f"Could not reach OpenAI: {redact(str(e), key)}")
        if resp.status_code >= 400:
            return _result("openai", model, message=f"OpenAI answered {describe_http_error(resp, key)}.")
        ids = sorted(m.get("id", "") for m in resp.json().get("data", []))
        available = model in ids
        vision_like = [i for i in ids if i.startswith(("gpt-4", "gpt-5", "o"))]
        return _result(
            "openai", model, ok=True, model_available=available, available_models=vision_like,
            message=("Key accepted and the model is available." if available else
                     f"Key accepted, but the model '{model}' is not available to it. Set OPENAI_MODEL to one of available_models."),
        )

    return _result(provider, "-", message=f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}'. Use mock, gemini or openai.")
