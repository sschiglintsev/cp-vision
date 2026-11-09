from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.models.detection import CameraSourceType, DetectionResult
from app.services.detection_service import detection_service

router = APIRouter()


@router.post("/detect", response_model=DetectionResult)
async def detect(
    file: UploadFile = File(...),
    camera_id: Optional[str] = Form(default=None),
    source_type: Optional[str] = Form(default=None),
    source_name: Optional[str] = Form(default=None),
) -> DetectionResult:
    """Выполнить распознавание объектов на изображении.

    Поля multipart/form-data:
    - file (required):   JPEG или PNG изображение.
    - camera_id:         ID источника/камеры (deviceId из браузера и т.п.).
    - source_type:       Тип источника: browser | usb | rtsp | robot | unknown.
    - source_name:       Человекочитаемое название источника.

    Возвращает DetectionResult с объектами и метаданными.
    Обратная совместимость: запросы без camera_id и source_type продолжают работать.
    """
    # Конвертируем строку source_type в enum; неизвестные значения → UNKNOWN
    src_type = CameraSourceType.UNKNOWN
    if source_type:
        try:
            src_type = CameraSourceType(source_type)
        except ValueError:
            src_type = CameraSourceType.UNKNOWN

    image_bytes = await file.read()

    return detection_service.detect(
        image_bytes=image_bytes,
        camera_id=camera_id,
        source_type=src_type,
        source_name=source_name,
    )
