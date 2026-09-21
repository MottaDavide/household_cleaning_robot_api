from src.app.schemas import CustomBase
from pydantic import Field, StrictInt

class MapResponse(CustomBase):
    rows: StrictInt
    cols: StrictInt
    walkable_tiles: StrictInt
    
    
class TileSchema(CustomBase):
    x: StrictInt
    y: StrictInt
    walkable: bool
    dirty: bool | None = None
    
class JsonMapSchema(CustomBase):
    rows: int = Field(..., gt=0, strict=True)
    cols: int = Field(..., gt=0, strict=True)
    tiles: list[TileSchema]