from src.app.schemas import CustomBase

class HealthResponse(CustomBase):
    status: str
    