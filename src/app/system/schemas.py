from src.app.schemas import CustomBase

class HealthResponse(CustomBase):
    """The body of the health check, which is always the same."""
    status: str
    