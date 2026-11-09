"""
DetectionService — тонкий сервисный слой над DetectionPipeline.

Два метода:

  detect(image_bytes, ...)
    Принимает bytes (JPEG/PNG). Делегирует в pipeline.run().
    Используется endpoint POST /detect.

  detect_frame(frame: CameraFrame)
    Принимает CameraFrame от Camera Provider.
    Делегирует в pipeline.run_decoded() — без JPEG encode/decode.
    Используется USB/RTSP Camera Providers.

Singleton `detection_service` создаётся без загрузки модели.
Движок становится доступен после его регистрации в model_registry (в lifespan).
"""

import logging
from typing import Optional, TYPE_CHECKING

from app.inference.registry import model_registry
from app.models.detection import CameraSourceType, DetectionResult
from app.pipeline.decoder import ImageDecoder
from app.pipeline.detection_pipeline import DetectionPipeline
from app.pipeline.preprocessor import IdentityPreprocessor

if TYPE_CHECKING:
    from app.cameras.models import CameraFrame
    from app.inference.registry import ModelRegistry

logger = logging.getLogger(__name__)


class DetectionService:
    """Сервис обнаружения объектов. Делегирует обработку в DetectionPipeline."""

    def __init__(self, registry: "ModelRegistry") -> None:
        self._pipeline = DetectionPipeline(
            decoder=ImageDecoder(),
            preprocessor=IdentityPreprocessor(),
            registry=registry,
        )

    def detect(
        self,
        image_bytes: bytes,
        camera_id: Optional[str] = None,
        source_type: CameraSourceType = CameraSourceType.UNKNOWN,
        source_name: Optional[str] = None,
    ) -> DetectionResult:
        """Выполнить обнаружение объектов и вернуть универсальный результат.

        Делегирует в DetectionPipeline:
        1. ImageDecoder декодирует изображение один раз.
        2. IdentityPreprocessor передаёт изображение без изменений.
        3. YoloEngine выполняет инференс на RGB-массиве.
        4. YoloPostprocessor конвертирует результаты в DetectedObject.
        5. Pipeline формирует DetectionResult.

        Args:
            image_bytes:  Содержимое изображения в байтах.
            camera_id:    Идентификатор источника (deviceId из браузера и т.п.).
            source_type:  Тип источника (browser / usb / rtsp / robot / unknown).
            source_name:  Человекочитаемое название источника (опционально).

        Returns:
            DetectionResult — объекты + метаданные источника, изображения, модели.

        Raises:
            ImageDecodeError: Если изображение не удалось декодировать.
            RuntimeError: Если движок не зарегистрирован или не готов.
        """
        return self._pipeline.run(
            image_bytes=image_bytes,
            camera_id=camera_id,
            source_type=source_type,
            source_name=source_name,
        )

    def detect_frame(self, frame: "CameraFrame") -> DetectionResult:
        """Выполнить детекцию на кадре от Camera Provider.

        Передаёт DecodedImage напрямую в pipeline.run_decoded().
        Гарантирует отсутствие JPEG encode/decode для USB и других провайдеров.

        Метаданные (camera_id, source.type, source.name) берутся из frame.source.

        Args:
            frame: CameraFrame, полученный от BaseCameraProvider.read().

        Returns:
            DetectionResult — объекты + метаданные источника, изображения, модели.

        Raises:
            RuntimeError: Если движок не зарегистрирован или не готов.
        """
        return self._pipeline.run_decoded(
            decoded=frame.image,
            camera_id=frame.camera_id,
            source_type=frame.source.type,
            source_name=frame.source.name,
        )


# Singleton — использует model_registry, который заполняется в lifespan.
# Загрузки модели при импорте НЕ происходит.
detection_service = DetectionService(registry=model_registry)
