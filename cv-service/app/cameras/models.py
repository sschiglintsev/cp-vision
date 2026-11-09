"""
CameraFrame — один кадр, полученный от Camera Provider.

Содержит уже декодированное RGB-изображение (DecodedImage) и метаданные:
- camera_id  — стабильный логический ID камеры в системе CP Vision;
- source     — тип и идентификатор источника (usb / rtsp / browser / ...);
- image      — декодированный RGB NumPy-массив + размеры;
- timestamp  — Unix milliseconds момента захвата кадра;
- sequence   — порядковый номер кадра в текущей сессии (1-based).

Принципиально важно:
- CameraFrame создаётся провайдером и передаётся в DetectionPipeline напрямую.
- Не требует JPEG-кодирования и обратного декодирования.
- Один экземпляр провайдера сохраняет один camera_id на протяжении жизненного цикла.
- sequence сбрасывается при создании нового экземпляра провайдера.
"""

import time
from dataclasses import dataclass, field

from app.models.detection import SourceMetadata
from app.models.image import DecodedImage


@dataclass
class CameraFrame:
    """Один кадр, полученный от Camera Provider.

    Attributes:
        camera_id:  Стабильный логический ID камеры в CP Vision.
                    Не меняется между кадрами одного провайдера.
        source:     Метаданные источника (тип, id, name).
        image:      Декодированное изображение: RGB array + размеры.
                    Создаётся провайдером — не требует повторного декодирования.
        timestamp:  Unix milliseconds момента захвата кадра.
        sequence:   Порядковый номер кадра в текущей сессии (начиная с 1).
                    Сбрасывается при создании нового экземпляра провайдера.
    """

    camera_id: str
    source: SourceMetadata
    image: DecodedImage
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    sequence: int = 0
