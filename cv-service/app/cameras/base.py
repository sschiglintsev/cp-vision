"""
BaseCameraProvider — абстрактный интерфейс источника видеопотока.

Описывает жизненный цикл источника:
  open() → read() × N → close()

Поддерживает контекстный менеджер:
  with provider:
      frame = provider.read()

Провайдер не знает:
- о YOLO или любой ML-модели;
- о ModelRegistry;
- о DetectionPipeline;
- о Frontend или Backend.

Его единственная ответственность — предоставить CameraFrame.

Реализации:
- USBCameraProvider (cameras/usb.py) — OpenCV VideoCapture.
- BrowserCameraProvider, RTSPCameraProvider, RobotCameraProvider — в будущих этапах.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.cameras.models import CameraFrame
from app.models.detection import SourceMetadata


class BaseCameraProvider(ABC):
    """Абстрактный интерфейс источника видеопотока."""

    @abstractmethod
    def open(self) -> None:
        """Открыть источник видеопотока и подготовить его к чтению.

        Вызывается один раз перед первым read().

        Raises:
            CameraOpenError: Если устройство недоступно или не удалось
                             выполнить тестовое чтение.
        """

    @abstractmethod
    def read(self) -> Optional[CameraFrame]:
        """Получить следующий кадр.

        Returns:
            CameraFrame с декодированным RGB-изображением, или None
            если кадр не удалось получить (timeout, конец потока и т.д.).

        Raises:
            CameraReadError: При критической ошибке чтения (устройство отключилось).
        """

    @abstractmethod
    def close(self) -> None:
        """Освободить все ресурсы источника.

        Безопасен для повторного вызова — не должен выбрасывать исключение
        если источник уже закрыт.
        """

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """True если источник открыт и готов к чтению."""

    @property
    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Метаданные источника: тип, логический ID, имя."""

    # ------------------------------------------------------------------
    # Контекстный менеджер — удобно для однокадровых и тестовых сценариев
    # ------------------------------------------------------------------

    def __enter__(self) -> "BaseCameraProvider":
        self.open()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()
