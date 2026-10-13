from fastapi import APIRouter, Depends
from app.core.security import require_api_key
from app.api.routes import health, projects, uploads, analysis, scale, equipment, points, geometry, calculations, ai

api_router = APIRouter(prefix="/api")

# Health stays public so hosting platforms can probe it; everything else needs the API key (when one is configured).
api_router.include_router(health.router)

protected = APIRouter(dependencies=[Depends(require_api_key)])
protected.include_router(projects.router)
protected.include_router(uploads.router)
protected.include_router(analysis.router)
protected.include_router(scale.router)
protected.include_router(equipment.router)
protected.include_router(points.router)
protected.include_router(geometry.router)
protected.include_router(calculations.router)
protected.include_router(ai.router)
api_router.include_router(protected)
