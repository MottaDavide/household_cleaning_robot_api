from src.app.schemas import CustomBase
from pydantic import Field

class MapResponse(CustomBase):
    rows: int
    cols: int
    walkable_tiles: int
    
    
class TileSchema(CustomBase):
    x: int
    y: int
    walkable: bool
    dirty: bool | None = None
    
class JsonMapSchema(CustomBase):
    rows: int = Field(..., gt=0)
    cols: int = Field(..., gt=0)
    tiles: list[TileSchema]