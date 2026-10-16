"""Suggests a scale calibration by reading a dimension label off the drawing.

The AI only reports what is printed on the plan: the two ends of a dimension line and the number written on
it. The result is a *suggestion*: it is never saved here, the user checks it against the drawing and confirms.
It is validated like a hand-made calibration, and anything implausible is rejected rather than guessed.
"""
import base64
import json
import math
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.scale_service import (
    MAX_MM_PER_PIXEL,
    MIN_MM_PER_PIXEL,
    MIN_REFERENCE_PIXELS,
    analysis_image_path,
    image_size,
)
from app.services.vision_service import (
    VisionProviderError,
    _format_error,
    describe_http_error,
    gemini_model_path,
    post_with_retry,
)

UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
MIN_CONFIDENCE = 0.6
GRID = 1000.0

PROMPT = """
You are reading an architectural floor plan to calibrate its scale.
Find ONE dimension line that has a clearly legible numeric label (for example "4500", "3.60", "450 cm"), ideally
a long one along an outer wall or across a large room. Do NOT use area figures (m2), levels/elevations, room
numbers, door/window schedule codes or scale text such as "1:100".

Return ONLY this JSON:
{
  "found": true,
  "point_a": [x, y],
  "point_b": [x, y],
  "label_text": "4500",
  "value": 4500,
  "unit": "mm",
  "confidence": 0.9,
  "note": "short description of which dimension this is"
}
- point_a and point_b are the two END points of the measured distance as [x, y] on a 0 to 1000 grid laid over the
  whole image (x = 0 at the left edge and 1000 at the right edge; y = 0 at the top edge and 1000 at the bottom
  edge): the places where the dimension line's end ticks/arrows touch the walls.
- "value" is the number printed on the drawing, exactly as written. "unit" is "mm", "cm" or "m". If no unit is
  printed, infer it ONLY when certain: plain whole numbers of 3 or more digits on metric plans are mm; numbers
  with a decimal point and 1-2 digits before it are m. If you are not sure, set "found" to false.
- If no dimension is clearly legible, return {"found": false, "note": "why"}. Never invent a number.
"""


def _validate(raw: Dict[str, Any], width: int, height: int) -> Dict[str, Any]:
    """Turn the model's answer into a checked suggestion, or raise ValueError with the reason."""
    if not raw.get("found"):
        raise ValueError(raw.get("note") or "No dimension with a legible number was found on the drawing.")

    try:
        # the model answers on a 0-1000 grid (its native convention); the app works in 0-1 ratios
        ax, ay = (float(v) / GRID for v in raw["point_a"])
        bx, by = (float(v) / GRID for v in raw["point_b"])
        value = float(raw["value"])
        unit = str(raw["unit"]).strip().lower()
        confidence = float(raw.get("confidence", 0))
    except (KeyError, TypeError, ValueError):
        raise ValueError("The AI's answer was incomplete, so no scale was suggested.")

    if unit not in UNIT_TO_MM:
        raise ValueError(f"The unit '{unit}' on the drawing is not one of mm, cm or m.")
    if not all(0.0 <= v <= 1.0 for v in (ax, ay, bx, by)):
        raise ValueError("The AI placed the dimension outside the drawing.")
    if value <= 0:
        raise ValueError("The dimension value must be positive.")
    if confidence < MIN_CONFIDENCE:
        raise ValueError(f"The AI was not confident enough about the dimension ({confidence:.0%}). Calibrate by hand.")

    real_mm = value * UNIT_TO_MM[unit]
    if real_mm > 200_000:
        raise ValueError("The dimension is longer than 200 m, which is not plausible.")
    ref_px = math.hypot((ax - bx) * width, (ay - by) * height)
    if ref_px < MIN_REFERENCE_PIXELS:
        raise ValueError("The two ends the AI found are too close together to give a reliable scale.")
    mm_per_px = real_mm / ref_px
    if not (MIN_MM_PER_PIXEL <= mm_per_px <= MAX_MM_PER_PIXEL):
        raise ValueError(
            f"Reading {raw.get('label_text') or value} {unit} between those points gives {mm_per_px:.2f} mm per "
            "pixel, which is not plausible for a building plan, so it was not suggested."
        )

    return {
        "point_a": {"x_ratio": round(ax, 5), "y_ratio": round(ay, 5)},
        "point_b": {"x_ratio": round(bx, 5), "y_ratio": round(by, 5)},
        "real_distance_mm": round(real_mm, 1),
        "label_text": str(raw.get("label_text") or f"{value:g} {unit}"),
        "unit": unit,
        "confidence": round(confidence, 2),
        "note": str(raw.get("note") or ""),
        "scale_mm_per_pixel": round(mm_per_px, 4),
    }


async def _ask_gemini(encoded: str) -> Dict[str, Any]:
    if not settings.GEMINI_API_KEY:
        raise VisionProviderError("AI_PROVIDER is 'gemini' but GEMINI_API_KEY is not configured.")
    url = f"https://generativelanguage.googleapis.com/v1beta/{gemini_model_path(settings.GEMINI_MODEL)}:generateContent"
    headers = {"x-goog-api-key": settings.GEMINI_API_KEY, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/png", "data": encoded}}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0},
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await post_with_retry(client, url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise VisionProviderError(
            f"Gemini rejected the request ({describe_http_error(response, settings.GEMINI_API_KEY)})."
        )
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise VisionProviderError("Gemini returned no answer.")
    return json.loads(candidates[0]["content"]["parts"][0]["text"])


async def _ask_openai(encoded: str) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        raise VisionProviderError("AI_PROVIDER is 'openai' but OPENAI_API_KEY is not configured.")
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": settings.OPENAI_MODEL,
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
        ]}],
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await post_with_retry(client, "https://api.openai.com/v1/chat/completions",
                                         headers=headers, json=payload)
    if response.status_code >= 400:
        raise VisionProviderError(
            f"OpenAI rejected the request ({describe_http_error(response, settings.OPENAI_API_KEY)})."
        )
    return json.loads(response.json()["choices"][0]["message"]["content"])


async def suggest_scale(project) -> Dict[str, Any]:
    """Returns a validated suggestion. Raises ValueError (nothing usable found) or VisionProviderError."""
    provider = settings.AI_PROVIDER.strip().lower()
    if provider == "mock":
        raise ValueError("The demo AI provider cannot read a drawing. Calibrate the scale by hand.")
    if provider not in ("gemini", "openai"):
        raise VisionProviderError(f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}'.")

    path = analysis_image_path(project)
    width, height = image_size(path)
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    try:
        raw = await (_ask_gemini(encoded) if provider == "gemini" else _ask_openai(encoded))
    except VisionProviderError:
        raise
    except Exception as e:
        key = settings.GEMINI_API_KEY if provider == "gemini" else settings.OPENAI_API_KEY
        message = _format_error(provider.title(), e, key)
        logger.error(f"Scale suggestion failed: {message}")
        raise VisionProviderError(f"Could not read the scale from the drawing: {message}") from None
    if not isinstance(raw, dict):
        raise ValueError("The AI's answer could not be understood.")
    return _validate(raw, width, height)
