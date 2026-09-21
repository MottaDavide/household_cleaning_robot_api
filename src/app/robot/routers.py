from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from src.app.robot.schemas import CleanRequest, CleanReport
from src.app.robot.services import execute_cleaning_session, generate_csv_history
from src.app.robot.exceptions import NoMapLoadedError, InvalidStartCoordinateError, CollisionError, InvalidDurationError
router = APIRouter(tags=["robot"])

@router.post("/clean", status_code=status.HTTP_200_OK, response_model=CleanReport, summary="Report of the cleaning task")
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=e.report.model_dump(mode='json') # pdf dice che vuole body=report
        ) from e
        
        
@router.get("/history", status_code=status.HTTP_200_OK, summary="Download cleaning-session history as RFC 4180-compatible CSV.")
async def get_history() -> Response:
    try: # probabilmente potrei farne a meno del try. Tanto va anche con lista vuota...
        csv_content = generate_csv_history()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Imposiible to generate the downloadable history",
        ) from e
        
    return Response(content=csv_content, media_type="text/csv")