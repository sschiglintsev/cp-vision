import logging
from io import BytesIO

import numpy as np
from PIL import Image
from ultralytics import YOLO

from app.models.detection import DetectedObject, DetectionResponse
from app.utils.config import settings

logger = logging.getLogger(__name__)


class YoloDetectionService:
    def __init__(self) -> None:
        logger.info("Loading YOLO model: %s", settings.yolo_model)
        self._model = YOLO(settings.yolo_model)
        logger.info("YOLO model loaded successfully")

    def detect(self, image_bytes: bytes) -> DetectionResponse:
        pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_array = np.array(pil_image)

        results = self._model(image_array, conf=settings.yolo_confidence, verbose=False)

        objects: list[DetectedObject] = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = xyxy
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                class_name = self._model.names.get(class_id, str(class_id))

                objects.append(
                    DetectedObject(
                        **{
                            "class": class_name,
                            "confidence": round(confidence, 4),
                            "x": int(x1),
                            "y": int(y1),
                            "width": int(x2 - x1),
                            "height": int(y2 - y1),
                        }
                    )
                )

        return DetectionResponse(objects=objects)


detection_service = YoloDetectionService()
