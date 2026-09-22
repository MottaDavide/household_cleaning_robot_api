from fastapi import APIRouter, status
from src.app.system.schemas import HealthResponse



router = APIRouter(
    tags=["system"]
)

@router.get("/health", status_code = status.HTTP_200_OK, response_model = HealthResponse, summary="health check: always return 'status': 'ok'")
async def get_health_check() -> HealthResponse:
    """Report that the service is up and able to answer requests.

    Fixed and cheap, and independent of whether a map has been loaded, so it
    can be used to tell that the service has finished starting up.
    """
    return HealthResponse(status="ok")