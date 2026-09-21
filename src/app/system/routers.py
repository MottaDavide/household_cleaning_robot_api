from fastapi import APIRouter, status
from src.app.system.schemas import HealthResponse



router = APIRouter(
    tags=["system"]
)

@router.get("/health", status_code = status.HTTP_200_OK, response_model = HealthResponse, summary="health check: alway return 'status': 'ok'")
async def get_health_check() -> HealthResponse:
    return HealthResponse(status="ok")