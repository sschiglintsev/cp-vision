"""
YoloPostprocessor — преобразует результаты Ultralytics YOLO в DetectedObject.

Не импортирует ultralytics напрямую — работает через duck typing.
Это позволяет:
- тестировать постобработку без загрузки модели;
- заменять или мокать результаты в тестах без ultralytics.

Используется исключительно внутри YoloEngine.
Не должен импортироваться из DetectionService или DetectionPipeline напрямую.
"""

from typing import Any, Dict, List

from app.models.detection import DetectedObject
from app.pipeline.postprocessor import BasePostprocessor


class YoloPostprocessor(BasePostprocessor):
    """Преобразует сырые результаты Ultralytics YOLO в DetectedObject.

    Принимает model_names (dict class_id → class_name) при создании,
    чтобы не зависеть от объекта модели при постобработке каждого кадра.

    Args:
        model_names: Словарь {class_id: class_name} из загруженной YOLO-модели.
    """

    def __init__(self, model_names: Dict[int, str]) -> None:
        self._names = model_names

    def process(self, raw_results: Any) -> List[DetectedObject]:
        """Извлечь bounding boxes из результатов YOLO.

        Работает через duck typing: не импортирует ultralytics.
        raw_results — список объектов с атрибутами .boxes, .xyxy, .cls, .conf.

        Args:
            raw_results: Список Results объектов от Ultralytics YOLO.

        Returns:
            Список DetectedObject с координатами в абсолютных пикселях.
        """
        objects: List[DetectedObject] = []

        for result in raw_results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = xyxy
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                class_name = self._names.get(class_id, str(class_id))

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

        return objects
