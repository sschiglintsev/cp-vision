"""
ImageDecoder — декодирует байты изображения в DecodedImage.

Декодирование происходит ровно один раз за запрос в рамках DetectionPipeline.
Поддерживает JPEG и PNG (любой формат, который понимает Pillow).

Результат — DecodedImage с:
- RGB numpy-массивом (H, W, 3), dtype uint8;
- реальными размерами (width, height);
- форматом исходного файла.
"""

import logging
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.models.image import DecodedImage

logger = logging.getLogger(__name__)


class ImageDecodeError(ValueError):
    """Невозможно декодировать изображение из переданных байтов.

    Возникает при:
    - пустом буфере;
    - нераспознанном формате изображения;
    - повреждённых данных.
    """


class ImageDecoder:
    """Декодирует bytes → DecodedImage.

    Stateless — один экземпляр потокобезопасно обслуживает параллельные запросы.
    Каждый вызов decode() создаёт независимый DecodedImage с собственным array.
    """

    def decode(self, image_bytes: bytes) -> DecodedImage:
        """Декодировать bytes в DecodedImage.

        Выполняет единственный Image.open() за запрос. Конвертирует в RGB
        для единообразия — JPEG обычно уже RGB, PNG с RGBA теряет альфа-канал.

        Args:
            image_bytes: Содержимое изображения (JPEG, PNG и т.д.)

        Returns:
            DecodedImage с пиксельным массивом и метаданными.

        Raises:
            ImageDecodeError: Если буфер пустой, формат нераспознан
                              или данные повреждены.
        """
        if not image_bytes:
            raise ImageDecodeError("Empty image bytes")

        try:
            pil_image = Image.open(BytesIO(image_bytes))
            image_format = (pil_image.format or "jpeg").lower()
            width, height = pil_image.size
            # Конвертируем в RGB — единый формат для всех движков.
            rgb_image = pil_image.convert("RGB")
            # np.array создаёт новый массив — не разделяется между запросами.
            array = np.array(rgb_image, dtype=np.uint8)
        except UnidentifiedImageError as exc:
            raise ImageDecodeError(f"Cannot identify image format: {exc}") from exc
        except ImageDecodeError:
            raise
        except Exception as exc:
            raise ImageDecodeError(f"Failed to decode image: {exc}") from exc

        logger.debug(
            "ImageDecoder: decoded %s %dx%d (%d bytes)",
            image_format, width, height, len(image_bytes),
        )

        return DecodedImage(
            array=array,
            width=width,
            height=height,
            format=image_format,
        )
