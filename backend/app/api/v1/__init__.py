from fastapi import APIRouter

from app.api.v1.routes import auth, conversations, documents, health, search, workspaces

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)
