from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, require_project_access
from app.core.security import require_api_key
from app.api.routes import health, projects, uploads, analysis, scale, equipment, points, geometry, calculations, ai, reports, auth

api_router = APIRouter(prefix="/api")

# Health stays public so hosting platforms can probe it; everything else needs the API key (when one is configured).
api_router.include_router(health.router)

protected = APIRouter(dependencies=[Depends(require_api_key)])
protected.include_router(auth.router)

# Everything below needs a signed-in user (when login is switched on), and anything under /projects/{project_id}
# must belong to that user.
owned = APIRouter(dependencies=[Depends(get_current_user), Depends(require_project_access)])
owned.include_router(projects.router)
owned.include_router(uploads.router)
owned.include_router(analysis.router)
owned.include_router(scale.router)
owned.include_router(equipment.router)
owned.include_router(points.router)
owned.include_router(geometry.router)
owned.include_router(calculations.router)
owned.include_router(ai.router)
owned.include_router(reports.router)
protected.include_router(owned)
api_router.include_router(protected)
