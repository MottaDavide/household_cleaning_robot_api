from src.app.schemas import CustomBase
from pydantic import Field
from uuid import UUID
from datetime import datetime
from enum import StrEnum


# pdf states there are 2 robot models
class RobotModel(CustomBase, StrEnum):
    BASIC = Field(default = "basic", description = "performs and reports a cleaning operation on every walkable tile it visits, even when that tile is already clean")
    PREMIUM = Field(defualt = "premium", description = "performs and reports a cleaning operation only when the visited tile is currently dirty. It skips a clean tile.")
    
    
# 4 directions (always from pdf)
class Direction(CustomBase, StrEnum):
    NORTH = 'norht'
    EAST = 'east'
    SOUTH = 'south'
    WEST = 'west'
    
MOVEMENT_DELTAS = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0)
}
    

class SessionState(CustomBase, StrEnum):
    COMPLETED = "completed"
    ERROR = "error"
    
    
class Coordinate(CustomBase):
    x: int
    y: int
    
class Action(CustomBase):
    direction: Direction
    steps: int = Field(..., gt=0)
    
class CleanRequest(CustomBase):
    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
    
class ErrorDetails(CustomBase):
    code: str = "collision" 
    message: str
    position: Coordinate

class CleanReport(CustomBase):
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
    