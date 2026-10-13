from fastapi import APIRouter
from app.api.routes import health, projects, uploads, analysis, scale, equipment, points

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(uploads.router)
api_router.include_router(analysis.router)
api_router.include_router(scale.router)
api_router.include_router(equipment.router)
api_router.include_router(points.router)
