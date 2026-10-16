"""
Shared API key protection for a deployed backend.

When `API_KEY` is set, every API route except `/api/health` requires the header `X-API-Key: <key>`.
When it is empty (local development, tests) protection is off.

This is a gate against casual abuse of a public instance (anonymous projects, uploads, AI credit),
NOT user authentication: anyone holding the key, including anyone who unpacks the mobile app that
embeds it, has full access. Per-user login is a separate piece of work.
"""
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import Settings, settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = settings.API_KEY
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def check_deployment_safety(cfg: Settings) -> None:
    """Refuse to start an unprotected production instance that can spend AI credit."""
    production = cfg.APP_ENV.strip().lower() == "production"
    real_provider = cfg.AI_PROVIDER.strip().lower() in ("gemini", "openai")
    if production and real_provider and not cfg.API_KEY:
        raise RuntimeError(
            "Refusing to start: APP_ENV=production with a real AI provider requires API_KEY to be set, "
            "otherwise anyone who finds the URL can spend your AI credit."
        )
    if production and not cfg.AUTH_SECRET:
        raise RuntimeError(
            "Refusing to start: APP_ENV=production requires AUTH_SECRET (a long random string, different from "
            "API_KEY) so that every user signs in and sees only their own projects."
        )
