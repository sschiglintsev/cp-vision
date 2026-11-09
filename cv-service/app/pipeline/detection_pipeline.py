"""
DetectionPipeline — конвейер обработки изображения для детекции объектов.

Два точки входа:

  run(image_bytes, ...)
    Принимает bytes (JPEG/PNG). Декодирует через ImageDecoder.
    Используется endpoint POST /detect (Browser Camera через Socket.IO).

  run_decoded(decoded: DecodedImage, ...)
    Принимает уже декодированный DecodedImage — декодирование пропускается.
    Используется Camera Providers (USB, RTSP и т.д.), которые уже имеют
    NumPy-массив и не должны выполнять JPEG encode/decode.

Гарантии:
- Изображение декодируется не более одного раза за запрос.
- Каждый запрос имеет собственный DecodedImage — смешивания данных между
  параллельными запросами не происходит.
- Pipeline не зависит от YOLO или любой конкретной ML-библиотеки.
- Pipeline не зависит от источника видеопотока.

DetectionService — тонкий сервисный слой над Pipeline, добавляет метаданные.
"""

import logging
from typing import Optional, TYPE_CHECKING

from app.models.detection import (
    CameraSourceType,
    DetectionResult,
    ImageMetadata,
    ModelMetadata,
    SourceMetadata,
)
from app.models.image import DecodedImage
from app.pipeline.decoder import ImageDecoder
from app.pipeline.preprocessor import BasePreprocessor

if TYPE_CHECKING:
    from app.inference.registry import ModelRegistry

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Конвейер: Decode → Preprocess → Infer → Build DetectionResult.

    Не зависит от конкретной реализации движка (YOLO, ONNX и т.д.).
    Не зависит от источника изображения.
    """

    def __init__(
        self,
        decoder: ImageDecoder,
        preprocessor: BasePreprocessor,
        registry: "ModelRegistry",
    ) -> None:
        self._decoder = decoder
        self._preprocessor = preprocessor
        self._registry = registry

    def run(
        self,
        image_bytes: bytes,
        camera_id: Optional[str] = None,
        source_type: CameraSourceType = CameraSourceType.UNKNOWN,
        source_name: Optional[str] = None,
    ) -> DetectionResult:
        """Выполнить полный цикл обработки изображения.

        Args:
            image_bytes:  Содержимое изображения (JPEG, PNG).
            camera_id:    Идентификатор источника.
            source_type:  Тип источника (browser / usb / rtsp / robot / unknown).
            source_name:  Человекочитаемое название источника.

        Returns:
            DetectionResult с объектами и метаданными.

        Raises:
            ImageDecodeError: Если изображение не удалось декодировать.
            RuntimeError: Если движок не зарегистрирован или не готов.
        """
        # 1. Decode — один Image.open() за запрос
        decoded: DecodedImage = self._decoder.decode(image_bytes)

        # 2. Preprocess
        prepared: DecodedImage = self._preprocessor.process(decoded)

        # 3. Inference
        engine = self._registry.get_active_engine()
        objects = engine.detect(prepared)

        # 4. Build result
        # Используем размеры исходного (decoded) изображения — не preprocessed.
        # Это гарантирует корректные координаты независимо от того, изменяет ли
        # preprocessor размер изображения (для будущих resize-preprocessors).
        model_info = engine.get_model_info()

        logger.debug(
            "DetectionPipeline: %s %dx%d → %d objects",
            decoded.format, decoded.width, decoded.height, len(objects),
        )

        return DetectionResult(
            camera_id=camera_id,
            source=SourceMetadata(
                type=source_type,
                id=camera_id,
                name=source_name,
            ),
            image=ImageMetadata(
                width=decoded.width,
                height=decoded.height,
                format=decoded.format,
            ),
            model=ModelMetadata(
                id=model_info.get("id", "unknown"),
                name=model_info.get("name", "unknown"),
                type=model_info.get("type", "object-detection"),
            ),
            objects=objects,
        )

    def run_decoded(
        self,
        decoded: DecodedImage,
        camera_id: Optional[str] = None,
        source_type: CameraSourceType = CameraSourceType.UNKNOWN,
        source_name: Optional[str] = None,
    ) -> DetectionResult:
        """Выполнить конвейер с уже декодированным изображением.

        Используется Camera Providers (USB, RTSP и т.д.):
        - пропускает шаг ImageDecoder.decode() (изображение уже готово);
        - гарантирует отсутствие JPEG encode/decode для USB-кадров;
        - продолжает с шага Preprocess → Infer → Build.

        Args:
            decoded:      Декодированное изображение (RGB array + метаданные).
            camera_id:    Идентификатор источника.
            source_type:  Тип источника (usb / rtsp / browser / ...).
            source_name:  Человекочитаемое название источника.

        Returns:
            DetectionResult с объектами и метаданными.

        Raises:
            RuntimeError: Если движок не зарегистрирован или не готов.
        """
        # 1. Decode — пропускается (decoded уже готов)

        # 2. Preprocess
        prepared: DecodedImage = self._preprocessor.process(decoded)

        # 3. Inference
        engine = self._registry.get_active_engine()
        objects = engine.detect(prepared)

        # 4. Build result
        # Используем размеры исходного (decoded) изображения — не preprocessed.
        model_info = engine.get_model_info()

        logger.debug(
            "DetectionPipeline.run_decoded: %s %dx%d → %d objects",
            decoded.format, decoded.width, decoded.height, len(objects),
        )

        return DetectionResult(
            camera_id=camera_id,
            source=SourceMetadata(
                type=source_type,
                id=camera_id,
                name=source_name,
            ),
            image=ImageMetadata(
                width=decoded.width,
                height=decoded.height,
                format=decoded.format,
            ),
            model=ModelMetadata(
                id=model_info.get("id", "unknown"),
                name=model_info.get("name", "unknown"),
                type=model_info.get("type", "object-detection"),
            ),
            objects=objects,
        )
