"""
YoloEngine — реализация BaseInferenceEngine для YOLOv11n.

Инкапсулирует всю YOLO-специфичную логику:
- загрузку модели из ultralytics (только в initialize());
- приём DecodedImage и передачу array в YOLO (без повторного Image.open());
- постобработку результатов через YoloPostprocessor;
- порог уверенности из конфигурации.

Изменение в Stage 4:
    detect(image_bytes: bytes) → detect(image: DecodedImage)
    Движок больше не выполняет Image.open() — декодирование вынесено в ImageDecoder.
    YoloPostprocessor выделен в отдельный класс для независимого тестирования.
"""

import logging
from typing import Dict, List, Optional

from app.core.config import settings
from app.inference.base import BaseInferenceEngine
from app.models.detection import DetectedObject
from app.models.image import DecodedImage

logger = logging.getLogger(__name__)


class YoloEngine(BaseInferenceEngine):
    """Движок обнаружения объектов на базе YOLOv11n (Ultralytics)."""

    def __init__(self) -> None:
        self._model: Optional[object] = None
        self._postprocessor: Optional[object] = None
        self._ready: bool = False

    def initialize(self) -> None:
        """Загрузить модель YOLOv11n и подготовить постпроцессор.

        Вызывается один раз в lifespan. Импортирует ultralytics и YoloPostprocessor
        только здесь — не при импорте модуля.
        """
        from ultralytics import YOLO
        from app.inference.yolo_postprocessor import YoloPostprocessor

        logger.info("YoloEngine: loading model '%s'", settings.yolo_model)
        self._model = YOLO(settings.yolo_model)
        # YoloPostprocessor получает имена классов один раз — не при каждом кадре.
        self._postprocessor = YoloPostprocessor(model_names=dict(self._model.names))
        self._ready = True
        logger.info("YoloEngine: model loaded successfully")

    def detect(self, image: DecodedImage) -> List[DetectedObject]:
        """Выполнить YOLO-инференс и вернуть список обнаруженных объектов.

        Принимает DecodedImage с готовым RGB-массивом.
        Не выполняет Image.open() — декодирование выполнено ранее в ImageDecoder.

        Алгоритм:
        1. Получить image.array (RGB numpy array из ImageDecoder).
        2. Прогнать через YOLO с порогом уверенности из config.
        3. Передать сырые результаты в YoloPostprocessor.
        4. Вернуть список DetectedObject.

        Args:
            image: DecodedImage с array (H, W, 3) uint8, RGB.
        """
        if not self._ready or self._model is None or self._postprocessor is None:
            raise RuntimeError("YoloEngine is not initialized. Call initialize() first.")

        # image.array уже является RGB numpy array — повторное декодирование не нужно.
        results = self._model(image.array, conf=settings.yolo_confidence, verbose=False)
        return self._postprocessor.process(results)

    def get_model_info(self) -> Dict[str, str]:
        """Вернуть метаданные загруженной модели.

        Контракт ключей: id, name, type, framework.
        """
        model_id = settings.yolo_model.replace(".pt", "")  # "yolo11n"
        return {
            "id": model_id,
            "name": model_id,
            "type": "object-detection",
            "framework": "ultralytics",
        }

    def is_ready(self) -> bool:
        """Вернуть True если модель загружена и готова к инференсу."""
        return self._ready

    def shutdown(self) -> None:
        """Освободить ресурсы модели при остановке приложения."""
        self._model = None
        self._postprocessor = None
        self._ready = False
        logger.info("YoloEngine: shut down")
