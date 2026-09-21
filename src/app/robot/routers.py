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
    try: # probabilmente potrei farne a meno del try. Tanto va anche con lista vuota...
        csv_content = generate_csv_history()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Impossible to generate the downloadable history",
        ) from e
        
    return CsvResponse(content=csv_content, media_type="text/csv")