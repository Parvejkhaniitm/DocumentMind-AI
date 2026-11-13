from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Workspace-scoped document intelligence and retrieval API.",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
