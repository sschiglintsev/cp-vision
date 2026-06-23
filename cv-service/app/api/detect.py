from fastapi import APIRouter, File, UploadFile

from app.models.detection import DetectionResponse
from app.services.detection_service import detection_service

router = APIRouter()


@router.post("/detect", response_model=DetectionResponse)
async def detect(file: UploadFile = File(...)) -> DetectionResponse:
    image_bytes = await file.read()
    return detection_service.detect(image_bytes)
