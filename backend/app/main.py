from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.core.security import check_deployment_safety
from app.db.database import init_db
from app.db.owner_column import ensure_owner_column
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    check_deployment_safety(settings)
    if not settings.API_KEY:
        logger.warning("API_KEY is not set: the API is open to anyone who can reach it.")
    logger.info("Initializing VoltPlan database...")
    init_db()
    ensure_owner_column()
    if not settings.AUTH_SECRET:
        logger.warning("AUTH_SECRET is not set: per-user login is OFF and every project is visible to every caller.")
    logger.info(f"VoltPlan backend started. AI Provider: '{settings.AI_PROVIDER}', Standard: '{settings.DEFAULT_STANDARD}'")
    yield
    logger.info("VoltPlan backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="VoltPlan AI-Assisted Electrical Planning & BOQ Estimation API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.CORS_ORIGINS == ["*"] else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred while processing the engineering pipeline."},
    )


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "standard": settings.DEFAULT_STANDARD,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
