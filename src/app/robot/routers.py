from fastapi import APIRouter, HTTPException, status
from app.robot.schemas import CleanRequest, CleanReport
from app.robot.service import execute_cleaning_session
from app.robot.exceptions import NoMapLoadedError, InvalidStartCoordinateError, CollisionError

router = APIRouter(tags=["Robot"])

@router.post("/clean", status_code=status.HTTP_200_OK, response_model=CleanReport, summary="Report of the cleaning task")
def clean(request: CleanRequest):
    
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
            detail=e.report.model_dump(mode='json')
        ) from e