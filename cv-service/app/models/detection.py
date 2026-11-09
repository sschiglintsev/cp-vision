"""
Pydantic-модели для результатов распознавания объектов.

DetectedObject — отдельный обнаруженный объект (координаты в абсолютных пикселях).
DetectionResult — универсальный результат: объекты + метаданные источника, изображения, модели.

Контракт DetectedObject не изменён для обратной совместимости с Backend и Frontend.
"""

import time
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Объект распознавания — не изменять поля и алиасы (Backend/Frontend зависят от них)
# ---------------------------------------------------------------------------

class DetectedObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(alias="class", serialization_alias="class")
    confidence: float
    x: int
    y: int
    width: int
    height: int


# ---------------------------------------------------------------------------
# Метаданные источника видеопотока
# ---------------------------------------------------------------------------

class CameraSourceType(str, Enum):
    """Тип источника видеопотока."""
    BROWSER = "browser"
    USB = "usb"
    RTSP = "rtsp"
    ROBOT = "robot"
    UNKNOWN = "unknown"


class SourceMetadata(BaseModel):
    """Идентификация источника изображения."""
    type: CameraSourceType = CameraSourceType.UNKNOWN
    id: Optional[str] = None      # deviceId из браузера или идентификатор устройства
    name: Optional[str] = None    # человекочитаемое название


# ---------------------------------------------------------------------------
# Метаданные изображения
# ---------------------------------------------------------------------------

class ImageMetadata(BaseModel):
    """Параметры декодированного изображения."""
    width: int    # реальная ширина в пикселях
    height: int   # реальная высота в пикселях
    format: str = "jpeg"  # jpeg / png / ...


# ---------------------------------------------------------------------------
# Метаданные модели инференса
# ---------------------------------------------------------------------------

class ModelMetadata(BaseModel):
    """Идентификация и тип движка распознавания."""
    id: str    # уникальный идентификатор модели, напр. "yolo11n"
    name: str  # отображаемое название
    type: str  # "object-detection" | "classification" | ...


# ---------------------------------------------------------------------------
# Универсальный результат распознавания
# ---------------------------------------------------------------------------

class DetectionResult(BaseModel):
    """Универсальный результат распознавания — независим от модели и источника.

    Позволяет однозначно связать каждый результат с конкретной камерой,
    изображением и моделью. Поддерживает будущие источники (USB, RTSP, Robot).
    """
    schema_version: str = "1.0"
    camera_id: Optional[str] = None    # соответствует source.id
    source: SourceMetadata
    image: ImageMetadata
    model: ModelMetadata
    objects: List[DetectedObject]
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


# ---------------------------------------------------------------------------
# Оставлен для совместимости (используется только внутри сервиса)
# ---------------------------------------------------------------------------

class DetectionResponse(BaseModel):
    """Устаревшая обёртка. Используйте DetectionResult."""
    objects: List[DetectedObject]
