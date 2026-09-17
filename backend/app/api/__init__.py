from app.api.activities import router as activities_router
from app.api.projects import router as projects_router
from app.api.relationships import router as relationships_router
from app.api.wbs import router as wbs_router

__all__ = [
    "activities_router",
    "projects_router",
    "relationships_router",
    "wbs_router",
]
