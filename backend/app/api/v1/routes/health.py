from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse, summary="Check API liveness")
def get_health() -> HealthResponse:
    """Report that the API process is running; this does not check dependencies."""
    return HealthResponse(status="ok")
