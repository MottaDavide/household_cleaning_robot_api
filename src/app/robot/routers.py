from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from src.app.robot.schemas import CleanRequest, CleanReport, CsvResponse
from src.app.robot.services import execute_cleaning_session, generate_csv_history
from src.app.robot.exceptions import NoMapLoadedError, InvalidStartCoordinateError, CollisionError
router = APIRouter(tags=["robot"])

@router.post("/clean", status_code=status.HTTP_200_OK, response_model=CleanReport, summary="Report of the cleaning task",
             responses={
    409: {
        "description": "No map has been loaded, or a movement collided with an obstacle or the map boundary"
    },
    422: {
        "description": "Malformed request, or a start coordinate outside the map or non-walkable"
    },
},)
async def clean(request: CleanRequest):
    """Run a single cleaning session on the map that is currently loaded.

    The robot cleans the tile it starts on, then walks the requested actions
    one step at a time. A session that gets through every action returns a
    completed report. One that walks into an obstacle or off the edge of the
    map stops there and returns an error report with the same fields, so a
    client can read either outcome the same way. Both are added to the
    history.
    """
    
    try:
        return execute_cleaning_session(request)

    except NoMapLoadedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=str(e)
        ) from e
        
    except InvalidStartCoordinateError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, 
            detail=str(e)
        ) from e
        
    except CollisionError as e:
        return  JSONResponse(
            status_code=status.HTTP_409_CONFLICT, 
            content=e.report.model_dump(mode='json') # pdf dice che vuole body=report
        )
        
        
@router.get("/history", status_code=status.HTTP_200_OK, summary="Download cleaning-session history as RFC 4180-compatible CSV.",
            response_class = CsvResponse)
async def get_history() -> CsvResponse:
    """Download the history of every cleaning session as CSV.

    Sessions are listed oldest first, both those that completed and those
    that ended in a collision. A session rejected before it could start never
    ran, so it is not listed. The history survives a new map being loaded,
    and lasts as long as the running service.
    """
    csv_content = generate_csv_history()
    return CsvResponse(content=csv_content, media_type="text/csv")