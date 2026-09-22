from src.app.schemas import CustomBase
from pydantic import Field, StrictInt

class MapResponse(CustomBase):
    """The summary returned once a map has been accepted.

    The three numbers give the shape of the grid and how much of it the robot
    can actually reach.
    """
    rows: StrictInt
    cols: StrictInt
    walkable_tiles: StrictInt
    
    
class TileSchema(CustomBase):
    """One tile of a map given in JSON form.

    A walkable tile without ``dirty`` starts dirty, so the flag is only
    needed to say a tile is already clean. A tile that is not walkable may
    never be dirty, and setting the flag on one is refused.
    """
    x: StrictInt
    y: StrictInt
    walkable: bool
    dirty: bool | None = None
    
class JsonMapSchema(CustomBase):
    """A whole map as described by a JSON document.

    The tiles must fill the declared rectangle exactly: every coordinate in
    it once, none missing and none repeated.
    """
    rows: int = Field(..., gt=0, strict=True)
    cols: int = Field(..., gt=0, strict=True)
    tiles: list[TileSchema]