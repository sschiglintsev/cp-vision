"""
Preprocessor — интерфейс и базовая реализация предобработки изображения.

BasePreprocessor не зависит от YOLO или любой конкретной ML-библиотеки.
IdentityPreprocessor передаёт изображение без изменений.

Специализированные preprocessors (resize, letterbox, normalize) могут быть
добавлены в будущем как новые классы без изменения DetectionPipeline.

ВАЖНО: YOLO-специфичные преобразования (letterbox, нормализация пикселей)
выполняются внутри YoloEngine — не здесь. Общий preprocessor остаётся
независимым от конкретной модели.
"""

from abc import ABC, abstractmethod

from app.models.image import DecodedImage


class BasePreprocessor(ABC):
    """Интерфейс предобработки изображения перед инференсом.

    Не зависит от YOLO или любой ML-библиотеки.
    """

    @abstractmethod
    def process(self, image: DecodedImage) -> DecodedImage:
        """Подготовить изображение для передачи в Inference Engine.

        Args:
            image: Декодированное изображение из ImageDecoder.

        Returns:
            Подготовленное изображение. Может быть тем же объектом
            (IdentityPreprocessor) или новым (при resize, нормализации и т.д.).
        """


class IdentityPreprocessor(BasePreprocessor):
    """Передаёт изображение без изменений.

    Используется когда модель принимает изображение в исходном размере.

    YOLOv11n через Ultralytics выполняет собственный letterbox и нормализацию
    внутри YoloEngine.detect() — IdentityPreprocessor не должен их дублировать.
    """

    def process(self, image: DecodedImage) -> DecodedImage:
        """Вернуть изображение без изменений."""
        return image
