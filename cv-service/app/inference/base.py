"""
BaseInferenceEngine — абстрактный интерфейс для движков инференса.

Контракт не зависит от конкретной ML-библиотеки (YOLO, ONNX и др.).
Все движки реализуют этот интерфейс, что позволяет DetectionPipeline и
DetectionService работать с любым из них без изменения кода.

Изменение в Stage 4:
    detect(image_bytes: bytes) → detect(image: DecodedImage)
    Декодирование вынесено в ImageDecoder — движок получает уже готовый
    RGB-массив и не выполняет Image.open() повторно.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, TYPE_CHECKING

from app.models.detection import DetectedObject

if TYPE_CHECKING:
    from app.models.image import DecodedImage


class BaseInferenceEngine(ABC):
    """Базовый интерфейс для движков обнаружения объектов."""

    @abstractmethod
    def initialize(self) -> None:
        """Инициализировать движок: загрузить модель, подготовить ресурсы.

        Вызывается один раз при старте приложения (в lifespan).
        Не вызывается при импорте модуля.
        """

    @abstractmethod
    def detect(self, image: "DecodedImage") -> List[DetectedObject]:
        """Выполнить инференс на декодированном изображении.

        Принимает DecodedImage — изображение уже декодировано один раз в
        ImageDecoder. Движок не должен повторно вызывать Image.open().

        Args:
            image: Декодированное изображение (RGB array + метаданные).
                   Создаётся ImageDecoder, не изменяется между этапами Pipeline.

        Returns:
            Список обнаруженных объектов в универсальном формате.

        Raises:
            RuntimeError: Если движок не инициализирован (initialize() не вызван).
        """

    @abstractmethod
    def get_model_info(self) -> Dict[str, str]:
        """Вернуть информацию о модели (id, name, type, framework).

        Returns:
            Словарь с метаданными модели. Обязательные ключи: id, name, type.
        """

    @abstractmethod
    def is_ready(self) -> bool:
        """Проверить готовность движка к инференсу.

        Returns:
            True если модель загружена и готова.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Освободить ресурсы движка.

        Вызывается при остановке приложения (в lifespan).
        """
