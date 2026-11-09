"""
USBCameraProvider — получение кадров с физической USB-камеры через OpenCV.

Жизненный цикл:
    provider = USBCameraProvider(camera_id="usb-0", device_index=0)
    provider.open()           # Открывает VideoCapture, проверяет тестовым read
    frame = provider.read()   # BGR → RGB, возвращает CameraFrame
    provider.close()          # Освобождает VideoCapture

Контекстный менеджер:
    with USBCameraProvider(...) as provider:
        frame = provider.read()

Принципиально важно:
- BGR → RGB преобразование выполняется здесь, до передачи в Pipeline.
- Кадр передаётся как DecodedImage (NumPy array) без JPEG-кодирования.
- Камера НЕ открывается при импорте модуля.
- VideoCapture создаётся только в open().
"""

import logging
import time
from typing import Optional

import cv2
import numpy as np

from app.cameras.base import BaseCameraProvider
from app.cameras.exceptions import CameraOpenError
from app.cameras.models import CameraFrame
from app.models.detection import CameraSourceType, SourceMetadata
from app.models.image import DecodedImage

logger = logging.getLogger(__name__)


class USBCameraProvider(BaseCameraProvider):
    """Источник видеопотока: физическая USB-камера через OpenCV VideoCapture.

    Args:
        camera_id:     Логический ID камеры в CP Vision.
                       Стабилен на протяжении жизненного цикла провайдера.
        device_index:  Индекс устройства для cv2.VideoCapture (обычно 0 или 1).
        width:         Желаемое разрешение (ширина). OpenCV попытается установить.
        height:        Желаемое разрешение (высота). OpenCV попытается установить.
        fps:           Желаемая частота кадров. OpenCV попытается установить.
    """

    def __init__(
        self,
        camera_id: str = "usb-camera-0",
        device_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        self._camera_id = camera_id
        self._device_index = device_index
        self._requested_width = width
        self._requested_height = height
        self._requested_fps = fps

        # Заполняются после open() из реальных параметров устройства
        self._actual_width: int = width
        self._actual_height: int = height

        self._cap: Optional[cv2.VideoCapture] = None
        self._sequence: int = 0  # сбрасывается при создании нового экземпляра

    # ------------------------------------------------------------------
    # BaseCameraProvider interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Открыть USB-камеру и выполнить тестовое чтение.

        Устанавливает желаемые разрешение и FPS через CAP_PROP_*.
        Получает фактические параметры из первого кадра.
        Если устройство недоступно или первый read() неуспешен — CameraOpenError.

        Raises:
            CameraOpenError: Устройство не открылось или не читает кадры.
        """
        logger.info(
            "USBCameraProvider: opening device %d (camera_id='%s', requested %dx%d @%dfps)",
            self._device_index, self._camera_id,
            self._requested_width, self._requested_height, self._requested_fps,
        )

        cap = cv2.VideoCapture(self._device_index)

        if not cap.isOpened():
            raise CameraOpenError(
                f"Cannot open USB camera at device_index={self._device_index}. "
                "Check that the camera is connected and not in use."
            )

        # Запрашиваем желаемые параметры
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._requested_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._requested_height)
        cap.set(cv2.CAP_PROP_FPS, self._requested_fps)

        # Тестовое чтение — подтверждает, что камера реально работает
        ret, test_frame = cap.read()
        if not ret or test_frame is None or test_frame.size == 0:
            cap.release()
            raise CameraOpenError(
                f"USB camera at device_index={self._device_index} opened but failed to read "
                "first frame. Device may not be functioning correctly."
            )

        # Получаем фактические размеры из реального кадра
        self._actual_height, self._actual_width = test_frame.shape[:2]

        if (self._actual_width != self._requested_width or
                self._actual_height != self._requested_height):
            logger.warning(
                "USBCameraProvider: device %d does not support %dx%d, "
                "using actual %dx%d",
                self._device_index,
                self._requested_width, self._requested_height,
                self._actual_width, self._actual_height,
            )

        self._cap = cap
        self._sequence = 0
        logger.info(
            "USBCameraProvider: device %d opened as '%s' at actual %dx%d",
            self._device_index, self._camera_id,
            self._actual_width, self._actual_height,
        )

    def read(self) -> Optional[CameraFrame]:
        """Получить следующий кадр с камеры.

        Выполняет BGR → RGB преобразование перед созданием DecodedImage.
        Кадр передаётся в NumPy-массиве без JPEG-кодирования.

        Returns:
            CameraFrame с DecodedImage, или None если кадр не удалось получить.
        """
        if self._cap is None or not self._cap.isOpened():
            logger.debug("USBCameraProvider.read(): camera is not open")
            return None

        ret, bgr_frame = self._cap.read()

        if not ret or bgr_frame is None or bgr_frame.size == 0:
            logger.debug(
                "USBCameraProvider: failed to read frame from device %d",
                self._device_index,
            )
            return None

        # BGR → RGB: OpenCV возвращает BGR, Pipeline ожидает RGB
        rgb_array = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        h, w = rgb_array.shape[:2]

        decoded = DecodedImage(
            array=rgb_array,
            width=w,
            height=h,
            format="raw",  # кадр с камеры, не из файла
        )

        self._sequence += 1

        return CameraFrame(
            camera_id=self._camera_id,
            source=self.metadata,
            image=decoded,
            timestamp=int(time.time() * 1000),
            sequence=self._sequence,
        )

    def close(self) -> None:
        """Освободить VideoCapture.

        Безопасен для повторного вызова.
        """
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info(
                "USBCameraProvider: closed device %d ('%s')",
                self._device_index, self._camera_id,
            )

    @property
    def is_open(self) -> bool:
        """True если VideoCapture открыт и устройство доступно."""
        return self._cap is not None and self._cap.isOpened()

    @property
    def metadata(self) -> SourceMetadata:
        """Метаданные источника. source.type = usb."""
        return SourceMetadata(
            type=CameraSourceType.USB,
            id=self._camera_id,
            # OpenCV не предоставляет человекочитаемое имя устройства надёжно
            name=None,
        )

    # ------------------------------------------------------------------
    # Информационные свойства
    # ------------------------------------------------------------------

    @property
    def camera_id(self) -> str:
        """Логический ID камеры."""
        return self._camera_id

    @property
    def device_index(self) -> int:
        """Индекс устройства (для OpenCV)."""
        return self._device_index

    @property
    def actual_width(self) -> int:
        """Фактическая ширина кадра (после open())."""
        return self._actual_width

    @property
    def actual_height(self) -> int:
        """Фактическая высота кадра (после open())."""
        return self._actual_height
