from src.app.schemas import CustomBase
from pydantic import Field, StrictInt
from uuid import UUID
from datetime import datetime
from enum import StrEnum
from fastapi.responses import Response
from typing import Literal

# pdf states there are 2 robot models
class RobotModel(StrEnum):
    BASIC =  "basic"
    PREMIUM =  "premium"
    
    
# 4 directions (always from pdf)
class Direction(StrEnum):
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
    COMPLETED = "completed"
    ERROR = "error"
    
    
class Coordinate(CustomBase):
    x: StrictInt
    y: StrictInt
    
class Action(CustomBase):
    direction: Direction
    steps: int = Field(..., gt=0, strict=True)
    
class CleanRequest(CustomBase):
    start: Coordinate
    robot_model: RobotModel
    actions: list[Action]
    
class ErrorDetails(CustomBase):
    code: Literal["collision"] = "collision"
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
    
class CsvResponse(Response):
    media_type = "text/csv"
    