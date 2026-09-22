"""The cleaning engine, and the CSV export of everything it has done.

``execute_cleaning_session`` walks the robot across the current map and turns
the outcome into a report, whether it finished or hit a collision. Either way
the report is kept, and ``generate_csv_history`` renders the collected
reports as the history clients download.
"""

from src.app.robot.schemas import CleanReport, CleanRequest, MOVEMENT_DELTAS, Coordinate, Direction, ErrorDetails, RobotModel, SessionState
from src.app.robot.exceptions import CollisionError, NoMapLoadedError, InvalidStartCoordinateError
from src.app.core import state
import uuid
from datetime import datetime, UTC
import csv # RFC 4180
import io


def _process_tile(pos: tuple[int, int], robot_model: RobotModel, cleaned_tiles: list[Coordinate]) -> None:
    """Clean the tile the robot is standing on, if this robot would clean it.

    The one place the two models differ: a basic robot cleans every walkable
    tile it visits, a premium one only a tile that is genuinely dirty. Both
    effects happen in place -- the coordinate is appended to ``cleaned_tiles``
    and the tile's ``dirty`` flag is cleared in the current map.

    Args:
        pos: The tile the robot is on, as an ``(x, y)`` pair.
        robot_model: Which model is running the session.
        cleaned_tiles: The session's cleaned coordinates, appended to here.
    """
    is_dirty = state.current_map[pos]["dirty"]
    
    # come da pdf -> report basic su tutte le mattonelee, premium solo sulle sporche
    if robot_model == RobotModel.BASIC or is_dirty:
        cleaned_tiles.append(Coordinate(x=pos[0], y=pos[1]))
        
        # come da pdf se viene compiuta la polizia allora la mattonella non è più dirty
        state.current_map[pos]["dirty"] = False
        
        
def _create_report(
    session_id: uuid.UUID,
    started_at: datetime,
    robot_model: RobotModel,
    submitted_actions: int,
    successful_steps: int,
    cleaned_tiles: list[Coordinate],
    final_pos: tuple[int, int],
    error_details: ErrorDetails | None = None
) -> CleanReport:
    """Stamp a finished session with its end time and wrap it in a report.

    Called at both exits, the ordinary one and the collision one, so the two
    reports are built the same way. Passing ``error_details`` is what marks
    the session as an error rather than completed. The duration comes from
    the two wall-clock timestamps.

    Returns:
        The finished report, ready to be returned and stored.
    """
    finished_at = datetime.now(UTC)
    # durata in ms come da pdf è non negativo perchè finished è sempre maggiore di start
    duration_ms = int((finished_at - started_at).total_seconds() * 1000) 
    
    # come da pdf dobbiamo dire se il task è in errore (collisione) o completo
    session_state = SessionState.ERROR if error_details else SessionState.COMPLETED
    
    return CleanReport(
        id=session_id,
        started_at=started_at,
        finished_at=finished_at,
        state=session_state,
        robot_model=robot_model,
        submitted_actions=submitted_actions,
        successful_steps=successful_steps,
        cleaned_tiles=cleaned_tiles,
        final_position=Coordinate(x=final_pos[0], y=final_pos[1]), 
        duration_ms=duration_ms,
        error=error_details
    )

# preferisco separare le due casistiche "fuori mappa" e "tile non-walkable"
def _collision_message(pos):
    """Explain why the robot cannot enter a tile, or confirm that it can.

    Leaving the map and hitting an obstacle are both collisions but not the
    same mistake, so they get separate wording for the error report.

    Args:
        pos: The tile the robot is about to enter, as an ``(x, y)`` pair.
            It may be outside the map, which is one of the cases checked.

    Returns:
        A sentence describing the problem, or ``None`` if the move is legal.
    """
    if pos not in state.current_map:
        return "The robot cannot move outside the map."
    if not state.current_map[pos]["walkable"]:
        return "The robot cannot enter a non-walkable tile."
    return None

def execute_cleaning_session(request: CleanRequest) -> CleanReport:
    """Run one cleaning session across the map that is currently loaded.

    The starting tile is cleaned before the first action; after that each
    action runs one step at a time. A step that would leave the map or enter
    an obstacle ends the session there, keeping everything cleaned so far.

    Args:
        request: The start coordinate, robot model and actions. Actions may
            be empty, which still cleans the starting tile.

    Returns:
        The report of a session that finished every action.

    Raises:
        NoMapLoadedError: If no map has been uploaded yet.
        InvalidStartCoordinateError: If the start is outside the map or is
            not walkable.
        CollisionError: If a step would have left the map or hit an obstacle.
            Carries the report, which is appended to the history before the
            exception is raised.
    """
    started_at = datetime.now(UTC) # dovrebbe mantenere lo standard quando poi fastapi/pydantic passano al rispettivo json
    
    
    if state.current_map is None: # pdf parla di errore 409 quando la mappa non è caricata
        raise NoMapLoadedError("Map not found.")
    
    start_pos = (request.start.x, request.start.y)
    if start_pos not in state.current_map or not state.current_map[start_pos]["walkable"]: # pdf parla di 422 quando il punto di partenza è bad
        raise InvalidStartCoordinateError("Not a valid starting point.") 
    
    session_id = uuid.uuid4()
    current_pos = start_pos
    successful_steps = 0
    cleaned_tiles: list[Coordinate] = []
    
    # il pdf dice the starting tile is visited and processed before the first action;
    _process_tile(current_pos, request.robot_model, cleaned_tiles)
    
    
    for action in request.actions:
        dx, dy = MOVEMENT_DELTAS[action.direction]
        
        # each action is executed one step at a time; sempre da pdf
        for _ in range(action.steps):
            next_pos = (current_pos[0] + dx, current_pos[1] + dy)
            
            # da pdf: When the next step would enter a non-walkable tile or leave the map: stop before entering the invalid coordinate;
            collision = _collision_message(next_pos)
            if collision is not None:
                error = ErrorDetails(
                    message = collision, # error.message is a non-empty human-readable string.
                    position = Coordinate(x=next_pos[0], y=next_pos[1])  # error.position is the coordinate the robot attempted to enter, even when it is outside the map;
                )
                
                report = _create_report(
                    session_id=session_id, started_at=started_at, robot_model=request.robot_model,
                    submitted_actions=len(request.actions), successful_steps=successful_steps, cleaned_tiles=cleaned_tiles,
                    final_pos=current_pos, # leave final_position at the last valid coordinate;
                    error_details=error)
                state.session_history.append(report.model_dump(mode='json'))
                raise CollisionError(report)
            
            current_pos = next_pos
            successful_steps += 1
            _process_tile(current_pos, request.robot_model, cleaned_tiles)
            
    report = _create_report(
        session_id=session_id, started_at=started_at, robot_model=request.robot_model,
        submitted_actions=len(request.actions), successful_steps=successful_steps, cleaned_tiles=cleaned_tiles,
        final_pos=current_pos, # leave final_position at the last valid coordinate;
                    error_details=None)
    state.session_history.append(report.model_dump(mode='json'))

    return report


def generate_csv_history() -> str:
    """Render every session run so far as a single CSV document.

    Sessions come out oldest first, completed and interrupted alike. The
    columns are fixed, so a service that has run nothing still produces the
    header row and nothing after it. ``cleaned_tiles`` is written as a count
    rather than the list of coordinates, which would not fit one cell.

    Returns:
        The whole document as text, with rows separated as RFC 4180 asks.
    """
    f=io.StringIO()
    fieldnames = ["id","started_at","state","robot_model",
                "submitted_actions","successful_steps",
                "cleaned_tiles","duration_ms"]
    writer = csv.DictWriter(
        f=f,
        fieldnames=fieldnames
    )
    
    writer.writeheader()
    for session in state.session_history:
        writer.writerow(
            {'id': session['id'], 
             'started_at': session['started_at'],
             'state': session['state'],
             'robot_model': session['robot_model'],
             "submitted_actions": session['submitted_actions'],
             "successful_steps": session['successful_steps'],
             "cleaned_tiles" : len(session['cleaned_tiles']),
             "duration_ms": session['duration_ms']})
        
    return f.getvalue()

    
    
    