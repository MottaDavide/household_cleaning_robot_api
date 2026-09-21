from fastapi import APIRouter, status, UploadFile, HTTPException
from src.app.map.schemas import MapResponse
from src.app.map.services import process_map_upload
from src.app.map.exceptions import UnsupportedExtensionError, InvalidMapContentError



router = APIRouter(
    tags=["map"]
)

@router.put("/map", status_code = status.HTTP_200_OK, response_model = MapResponse, summary="extension, content and map validation according to the 'business' rules",
            responses={
    415: {"description": "The filename extension is not .txt or .json"},
    422: {"description": "The file contents do not describe a valid map"},
},)
async def upload_map(file: UploadFile ) -> MapResponse:
    filename = file.filename or ""
    
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Impossible to read the file."
        ) from e
        
    try:
        summary_dict = process_map_upload(filename, content)
        return MapResponse(**summary_dict)
    except UnsupportedExtensionError as e:
        # Errore come nel pdf (415) quando non c'è formato valido
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 
            detail=str(e)
        ) from e
        
    except InvalidMapContentError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, 
            detail=str(e)
        ) from e