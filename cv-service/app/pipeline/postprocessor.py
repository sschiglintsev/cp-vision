"""
BasePostprocessor — интерфейс постобработки результатов инференса.

Базовый интерфейс не зависит от YOLO или любой конкретной ML-библиотеки.

Реализации:
- YoloPostprocessor (inference/yolo_postprocessor.py) — преобразует результаты
  Ultralytics YOLO в DetectedObject через duck typing (без прямого импорта YOLO).

Архитектурное примечание:
--------------------------
BaseInferenceEngine.detect() возвращает List[DetectedObject] — постобработка
происходит внутри движка с помощью соответствующего Postprocessor.
DetectionPipeline получает готовый List[DetectedObject] от engine.detect(),
без необходимости знать детали формата конкретного движка.

Это позволяет DetectionService и DetectionPipeline оставаться независимыми
от Ultralytics API, формата Results и внутренней структуры YOLO.
"""

from abc import ABC, abstractmethod
from typing import Any, List

from app.models.detection import DetectedObject


class BasePostprocessor(ABC):
    """Интерфейс постобработки сырых результатов инференса.

    Не зависит от YOLO или любой конкретной ML-библиотеки.
    """

    @abstractmethod
    def process(self, raw_results: Any) -> List[DetectedObject]:
        """Преобразовать сырой результат инференса в список DetectedObject.

        Args:
            raw_results: Сырые результаты модели (специфичны для движка).
                         Тип Any обеспечивает независимость интерфейса от YOLO.

        Returns:
            Список обнаруженных объектов в универсальном формате DetectedObject.
        """
