from src.app.schemas import CustomBase
from pydantic import Field, StrictInt
from uuid import UUID
from datetime import datetime
from enum import StrEnum
from fastapi.responses import Response
from typing import Literal

# pdf states there are 2 robot models
class RobotModel(StrEnum):
    """The two robot models the service can run.

    Basic cleans every walkable tile it visits; premium skips a tile that is
    already clean.
    """
    BASIC =  "basic"
    PREMIUM =  "premium"
    
    
# 4 directions (always from pdf)
class Direction(StrEnum):
    """The four directions a robot can be asked to move in.

    The step each one stands for is written down in ``MOVEMENT_DELTAS``.
    """
    NORTH = 'north'
    EAST = 'east'
    SOUTH = 'south'
    WEST = 'west'
    
MOVEMENT_DELTAS = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0)
}
    

class SessionState(StrEnum):
    """How a cleaning session turned out.

    Completed if it got through every action, error if a collision stopped it.
    """
    COMPLETED = "completed"
    ERROR = "error"
    
    
class Coordinate(CustomBase):
    """A single tile on the map, in the grid's own coordinates.

    Zero-based, with ``(0, 0)`` at the top left, ``x`` growing east and ``y``
    growing south. Whole numbers only, so ``1.5`` or ``"1"`` is refused.
    """
    x: StrictInt
    y: StrictInt
    
class Action(CustomBase):
    """One instruction to move a number of steps in a single direction.

    Steps are taken one at a time rather than as a jump, so every tile along
    the way is visited and cleaned. The count must be a positive whole number.
    """
    direction: Direction
    steps: int = Field(..., gt=0, strict=True)
    
class CleanRequest(CustomBase):
    """Everything needed to run one cleaning session.

    All three parts are required, though ``actions`` may be empty: a session
    with no actions still cleans the tile it starts on. The start must be a
    walkable tile of the map currently loaded.
    """
    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
    
class ErrorDetails(CustomBase):
    """Why a cleaning session stopped before finishing.

    ``position`` is the tile the robot tried to enter and could not, so it is
    the one coordinate it never reached. It may sit outside the map, since
    walking off the edge is a collision just like hitting an obstacle.
    """
    code: Literal["collision"] = "collision"
    message: str
    position: Coordinate

class CleanReport(CustomBase):
    """The outcome of one cleaning session, whether it finished or not.

    ``successful_steps`` counts movements, so it excludes cleaning the
    starting tile. ``cleaned_tiles`` has one entry per cleaning operation in
    order, so a basic robot can repeat a coordinate. ``final_position`` is the
    last tile legitimately stood on, and ``error`` is set only on collision.
    """
    id: UUID 
    started_at: datetime 
    finished_at: datetime
    state: SessionState
    robot_model: RobotModel
    submitted_actions: int
    successful_steps: int
    cleaned_tiles: list[Coordinate]
    final_position: Coordinate
    duration_ms: int = Field(..., ge=0) 
    error: ErrorDetails | None = None 
    
class CsvResponse(Response):
    """A response class that marks its body as CSV rather than JSON.

    Used as the route's ``response_class`` so the generated documentation
    advertises ``text/csv`` for that endpoint.
    """
    media_type = "text/csv"
    