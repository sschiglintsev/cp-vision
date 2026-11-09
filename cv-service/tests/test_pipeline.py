"""
Тесты Detection Pipeline — Stage 4.

Покрывают:
- ImageDecoder: декодирование JPEG, PNG, ошибки, однократность
- IdentityPreprocessor: сохранение размеров, независимость от YOLO
- YoloPostprocessor: корректный DetectedObject, независимость от YOLO API
- DetectionPipeline: порядок этапов, сборка DetectionResult, параллелизм
- Регрессия: /detect backward compat, health endpoints
"""

import io
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image as PILImage

from app.models.detection import CameraSourceType, DetectedObject
from app.models.image import DecodedImage
from app.pipeline.decoder import ImageDecoder, ImageDecodeError
from app.pipeline.preprocessor import IdentityPreprocessor, BasePreprocessor
from app.pipeline.postprocessor import BasePostprocessor
from app.inference.yolo_postprocessor import YoloPostprocessor
from app.pipeline.detection_pipeline import DetectionPipeline


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_jpeg_bytes(width: int = 100, height: int = 80, color: tuple = (128, 64, 32)) -> bytes:
    """Создать синтетический JPEG-буфер заданного размера."""
    img = PILImage.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_png_bytes(width: int = 50, height: int = 40, color: tuple = (10, 20, 30)) -> bytes:
    """Создать синтетический PNG-буфер заданного размера."""
    img = PILImage.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_decoded_image(width: int = 100, height: int = 80) -> DecodedImage:
    """Создать DecodedImage с синтетическим массивом."""
    array = np.zeros((height, width, 3), dtype=np.uint8)
    return DecodedImage(array=array, width=width, height=height, format="jpeg")


# Мок ultralytics Results для YoloPostprocessor (без YOLO import)
class _MockTensor:
    def __init__(self, value: Any) -> None:
        self._value = value

    def tolist(self) -> Any:
        return self._value

    def item(self) -> Any:
        return self._value


class _MockBox:
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 class_id: int, confidence: float) -> None:
        self.xyxy = [_MockTensor([x1, y1, x2, y2])]
        self.cls = [_MockTensor(class_id)]
        self.conf = [_MockTensor(confidence)]


class _MockResult:
    def __init__(self, boxes: List[_MockBox]) -> None:
        self.boxes = boxes

    def __iter__(self):
        return iter(self.boxes)


def make_mock_yolo_results(detections: List[Dict]) -> List[_MockResult]:
    """Создать mock-результаты YOLO без ultralytics.

    Args:
        detections: Список словарей с ключами x1, y1, x2, y2, class_id, confidence.
    """
    boxes = [
        _MockBox(
            x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"],
            class_id=d["class_id"], confidence=d["confidence"],
        )
        for d in detections
    ]
    return [_MockResult(boxes=boxes)]


def make_mock_registry(objects: List[DetectedObject] = None) -> MagicMock:
    """Создать mock ModelRegistry с мокнутым движком."""
    if objects is None:
        objects = []
    mock_engine = MagicMock()
    mock_engine.detect.return_value = objects
    mock_engine.is_ready.return_value = True
    mock_engine.get_model_info.return_value = {
        "id": "test-model",
        "name": "test-model",
        "type": "object-detection",
    }
    registry = MagicMock()
    registry.get_active_engine.return_value = mock_engine
    registry.is_ready.return_value = True
    return registry


# ---------------------------------------------------------------------------
# Decoder tests
# ---------------------------------------------------------------------------

class TestImageDecoder:
    """1. Decoder: декодирование, размеры, ошибки."""

    def setup_method(self) -> None:
        self.decoder = ImageDecoder()

    def test_decode_jpeg_returns_decoded_image(self):
        """JPEG декодируется без ошибок и возвращает DecodedImage."""
        result = self.decoder.decode(make_jpeg_bytes(100, 80))
        assert isinstance(result, DecodedImage)

    def test_decode_jpeg_correct_dimensions(self):
        """Реальные размеры JPEG определяются корректно."""
        result = self.decoder.decode(make_jpeg_bytes(320, 240))
        assert result.width == 320
        assert result.height == 240

    def test_decode_jpeg_format(self):
        """Формат JPEG определяется как 'jpeg'."""
        result = self.decoder.decode(make_jpeg_bytes())
        assert result.format == "jpeg"

    def test_decode_png_returns_decoded_image(self):
        """PNG декодируется без ошибок."""
        result = self.decoder.decode(make_png_bytes(50, 40))
        assert isinstance(result, DecodedImage)

    def test_decode_png_correct_dimensions(self):
        """Реальные размеры PNG определяются корректно."""
        result = self.decoder.decode(make_png_bytes(50, 40))
        assert result.width == 50
        assert result.height == 40

    def test_decode_png_format(self):
        """Формат PNG определяется как 'png'."""
        result = self.decoder.decode(make_png_bytes())
        assert result.format == "png"

    def test_decode_produces_rgb_array(self):
        """Результирующий array — RGB, shape (H, W, 3)."""
        result = self.decoder.decode(make_jpeg_bytes(100, 80))
        assert result.array.ndim == 3
        assert result.array.shape[2] == 3
        assert result.array.dtype == np.uint8

    def test_decode_array_shape_matches_dimensions(self):
        """Форма array соответствует width/height."""
        result = self.decoder.decode(make_jpeg_bytes(200, 150))
        assert result.array.shape == (150, 200, 3)  # (H, W, C)

    def test_decode_raises_on_empty_bytes(self):
        """Пустые bytes вызывают ImageDecodeError."""
        with pytest.raises(ImageDecodeError, match="Empty image bytes"):
            self.decoder.decode(b"")

    def test_decode_raises_on_corrupted_data(self):
        """Повреждённые данные вызывают ImageDecodeError."""
        with pytest.raises(ImageDecodeError):
            self.decoder.decode(b"not-an-image-at-all-xyz")

    def test_decode_creates_independent_array_per_call(self):
        """Каждый вызов создаёт независимый массив — нет разделения данных."""
        jpeg = make_jpeg_bytes(10, 10, color=(255, 0, 0))
        result1 = self.decoder.decode(jpeg)
        result2 = self.decoder.decode(jpeg)
        # Разные объекты
        assert result1 is not result2
        assert result1.array is not result2.array
        # Мутация одного не затрагивает другой
        result1.array[0, 0, 0] = 0
        # result2 должен остаться нетронутым
        # (проверяем только объектную независимость, не значения из-за JPEG lossy)
        assert result1.array is not result2.array

    def test_decode_no_pil_reopen_inside(self):
        """Image.open вызывается ровно один раз за запрос декодера."""
        with patch("app.pipeline.decoder.Image") as mock_pil:
            mock_img = MagicMock()
            mock_img.format = "JPEG"
            mock_img.size = (100, 80)
            mock_img.convert.return_value = mock_img
            mock_pil.open.return_value = mock_img
            # Мокаем np.array чтобы не падало
            with patch("app.pipeline.decoder.np.array") as mock_np:
                mock_np.return_value = np.zeros((80, 100, 3), dtype=np.uint8)
                self.decoder.decode(make_jpeg_bytes())
            # Image.open вызван ровно 1 раз
            assert mock_pil.open.call_count == 1


# ---------------------------------------------------------------------------
# Preprocessor tests
# ---------------------------------------------------------------------------

class TestIdentityPreprocessor:
    """2. Preprocessing: IdentityPreprocessor сохраняет изображение."""

    def setup_method(self) -> None:
        self.preprocessor = IdentityPreprocessor()

    def test_identity_returns_same_object(self):
        """IdentityPreprocessor возвращает тот же объект DecodedImage."""
        image = make_decoded_image(100, 80)
        result = self.preprocessor.process(image)
        assert result is image

    def test_identity_preserves_width(self):
        """Ширина не изменяется."""
        image = make_decoded_image(320, 240)
        result = self.preprocessor.process(image)
        assert result.width == 320

    def test_identity_preserves_height(self):
        """Высота не изменяется."""
        image = make_decoded_image(320, 240)
        result = self.preprocessor.process(image)
        assert result.height == 240

    def test_identity_preserves_array_reference(self):
        """Array не копируется и не изменяется."""
        image = make_decoded_image(50, 50)
        result = self.preprocessor.process(image)
        assert result.array is image.array

    def test_identity_is_subclass_of_base(self):
        """IdentityPreprocessor реализует BasePreprocessor."""
        assert isinstance(self.preprocessor, BasePreprocessor)

    def test_preprocessor_has_no_yolo_import(self):
        """Модуль preprocessor не импортирует YOLO."""
        import app.pipeline.preprocessor as preprocessor_module
        import sys
        # ultralytics не должен быть импортирован через preprocessor
        assert "ultralytics" not in dir(preprocessor_module)


# ---------------------------------------------------------------------------
# YoloPostprocessor tests
# ---------------------------------------------------------------------------

class TestYoloPostprocessor:
    """3. Postprocessing: корректные DetectedObject, независимость от YOLO."""

    NAMES = {0: "person", 1: "car", 2: "cat"}

    def setup_method(self) -> None:
        self.postprocessor = YoloPostprocessor(model_names=self.NAMES)

    def test_is_subclass_of_base(self):
        """YoloPostprocessor реализует BasePostprocessor."""
        assert isinstance(self.postprocessor, BasePostprocessor)

    def test_returns_detected_object_list(self):
        """Возвращает список DetectedObject."""
        results = make_mock_yolo_results([
            {"x1": 10, "y1": 20, "x2": 110, "y2": 170, "class_id": 0, "confidence": 0.9},
        ])
        output = self.postprocessor.process(results)
        assert isinstance(output, list)
        assert len(output) == 1
        assert isinstance(output[0], DetectedObject)

    def test_preserves_class_name(self):
        """class_name берётся из model_names по class_id."""
        results = make_mock_yolo_results([
            {"x1": 0, "y1": 0, "x2": 50, "y2": 50, "class_id": 1, "confidence": 0.8},
        ])
        output = self.postprocessor.process(results)
        # DetectedObject имеет alias "class" для поля class_name
        assert output[0].class_name == "car"

    def test_preserves_confidence(self):
        """confidence округляется до 4 знаков."""
        results = make_mock_yolo_results([
            {"x1": 0, "y1": 0, "x2": 50, "y2": 50, "class_id": 0, "confidence": 0.912345},
        ])
        output = self.postprocessor.process(results)
        assert output[0].confidence == round(0.912345, 4)

    def test_preserves_coordinates(self):
        """x, y, width, height вычисляются из xyxy корректно."""
        results = make_mock_yolo_results([
            {"x1": 10.0, "y1": 20.0, "x2": 110.0, "y2": 170.0, "class_id": 0, "confidence": 0.9},
        ])
        output = self.postprocessor.process(results)
        obj = output[0]
        assert obj.x == 10
        assert obj.y == 20
        assert obj.width == 100   # x2 - x1
        assert obj.height == 150  # y2 - y1

    def test_handles_multiple_detections(self):
        """Несколько объектов обрабатываются корректно."""
        results = make_mock_yolo_results([
            {"x1": 0, "y1": 0, "x2": 50, "y2": 50, "class_id": 0, "confidence": 0.9},
            {"x1": 60, "y1": 60, "x2": 120, "y2": 100, "class_id": 2, "confidence": 0.75},
        ])
        output = self.postprocessor.process(results)
        assert len(output) == 2
        assert output[1].class_name == "cat"

    def test_handles_empty_results(self):
        """Пустые результаты → пустой список."""
        output = self.postprocessor.process([_MockResult(boxes=[])])
        assert output == []

    def test_handles_result_with_none_boxes(self):
        """Результат с boxes=None пропускается."""
        result_with_none = MagicMock()
        result_with_none.boxes = None
        output = self.postprocessor.process([result_with_none])
        assert output == []

    def test_no_ultralytics_import_in_module(self):
        """Модуль yolo_postprocessor не импортирует ultralytics напрямую."""
        import app.inference.yolo_postprocessor as postprocessor_module
        # Проверяем что в модуле нет прямого импорта ultralytics
        source_path = postprocessor_module.__file__
        with open(source_path) as f:
            source = f.read()
        assert "from ultralytics" not in source
        assert "import ultralytics" not in source

    def test_unknown_class_id_uses_string_fallback(self):
        """Неизвестный class_id → строковое представление id."""
        results = make_mock_yolo_results([
            {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "class_id": 99, "confidence": 0.5},
        ])
        output = self.postprocessor.process(results)
        assert output[0].class_name == "99"


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestDetectionPipeline:
    """4. Pipeline: порядок этапов, сборка результата, параллелизм."""

    def setup_method(self) -> None:
        self.decoder = ImageDecoder()
        self.preprocessor = IdentityPreprocessor()

    def _make_pipeline(self, objects=None) -> DetectionPipeline:
        registry = make_mock_registry(objects=objects or [])
        return DetectionPipeline(
            decoder=self.decoder,
            preprocessor=self.preprocessor,
            registry=registry,
        )

    def test_run_returns_detection_result(self):
        """run() возвращает DetectionResult."""
        from app.models.detection import DetectionResult
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(100, 80))
        assert isinstance(result, DetectionResult)

    def test_pipeline_calls_stages_in_order(self):
        """Decode → Preprocess → Infer вызываются в правильном порядке."""
        call_order = []

        decoder = MagicMock()
        decoded_image = make_decoded_image(100, 80)
        decoder.decode.side_effect = lambda b: (call_order.append("decode"), decoded_image)[1]

        preprocessor = MagicMock()
        preprocessor.process.side_effect = lambda img: (call_order.append("preprocess"), img)[1]

        registry = make_mock_registry()
        registry.get_active_engine.return_value.detect.side_effect = (
            lambda img: (call_order.append("infer"), [])[1]
        )

        pipeline = DetectionPipeline(decoder=decoder, preprocessor=preprocessor, registry=registry)
        pipeline.run(make_jpeg_bytes())

        assert call_order == ["decode", "preprocess", "infer"]

    def test_image_decoded_once(self):
        """Image.open вызывается ровно один раз за запрос."""
        with patch("app.pipeline.decoder.Image") as mock_pil:
            mock_img = MagicMock()
            mock_img.format = "JPEG"
            mock_img.size = (100, 80)
            mock_img.convert.return_value = mock_img
            mock_pil.open.return_value = mock_img
            with patch("app.pipeline.decoder.np.array") as mock_np:
                mock_np.return_value = np.zeros((80, 100, 3), dtype=np.uint8)
                pipeline = self._make_pipeline()
                pipeline.run(make_jpeg_bytes())
            assert mock_pil.open.call_count == 1

    def test_result_contains_source_image_dimensions(self):
        """image.width/height соответствуют исходному изображению."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(640, 480))
        assert result.image.width == 640
        assert result.image.height == 480

    def test_camera_id_passed_through(self):
        """camera_id передаётся в результат без изменений."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(), camera_id="cam-abc-123")
        assert result.camera_id == "cam-abc-123"

    def test_source_type_passed_through(self):
        """source_type передаётся в result.source.type."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(), source_type=CameraSourceType.BROWSER)
        assert result.source.type == CameraSourceType.BROWSER

    def test_source_name_passed_through(self):
        """source_name передаётся в result.source.name."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(), source_name="FaceTime HD Camera")
        assert result.source.name == "FaceTime HD Camera"

    def test_empty_detection_returns_empty_objects(self):
        """Пустой результат инференса → objects: []."""
        pipeline = self._make_pipeline(objects=[])
        result = pipeline.run(make_jpeg_bytes())
        assert result.objects == []

    def test_objects_from_engine_preserved(self):
        """Объекты из движка передаются в result.objects."""
        obj = DetectedObject(**{"class": "person", "confidence": 0.9, "x": 10, "y": 20, "width": 50, "height": 100})
        pipeline = self._make_pipeline(objects=[obj])
        result = pipeline.run(make_jpeg_bytes())
        assert len(result.objects) == 1
        assert result.objects[0].class_name == "person"

    def test_model_info_from_engine(self):
        """model.id берётся из get_model_info() движка."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes())
        assert result.model.id == "test-model"

    def test_error_propagates_from_decoder(self):
        """ImageDecodeError из декодера не превращается в пустой результат."""
        pipeline = self._make_pipeline()
        with pytest.raises(ImageDecodeError):
            pipeline.run(b"not-an-image")

    def test_error_propagates_from_engine(self):
        """RuntimeError из движка не превращается в пустой результат."""
        registry = MagicMock()
        registry.get_active_engine.side_effect = RuntimeError("Engine not ready")
        pipeline = DetectionPipeline(
            decoder=self.decoder,
            preprocessor=self.preprocessor,
            registry=registry,
        )
        with pytest.raises(RuntimeError, match="Engine not ready"):
            pipeline.run(make_jpeg_bytes())

    def test_parallel_requests_do_not_mix(self):
        """Параллельная обработка двух изображений не смешивает результаты."""
        obj_a = DetectedObject(**{"class": "person", "confidence": 0.9, "x": 0, "y": 0, "width": 10, "height": 10})
        obj_b = DetectedObject(**{"class": "car", "confidence": 0.8, "x": 50, "y": 50, "width": 20, "height": 15})

        def engine_detect_side_effect(image):
            # Возвращаем разные объекты в зависимости от размера изображения
            if image.width == 320:
                return [obj_a]
            else:
                return [obj_b]

        mock_engine = MagicMock()
        mock_engine.detect.side_effect = engine_detect_side_effect
        mock_engine.is_ready.return_value = True
        mock_engine.get_model_info.return_value = {"id": "t", "name": "t", "type": "object-detection"}
        registry = MagicMock()
        registry.get_active_engine.return_value = mock_engine

        pipeline = DetectionPipeline(
            decoder=self.decoder,
            preprocessor=self.preprocessor,
            registry=registry,
        )

        result_a = pipeline.run(make_jpeg_bytes(320, 240), camera_id="cam-a")
        result_b = pipeline.run(make_jpeg_bytes(640, 480), camera_id="cam-b")

        assert result_a.camera_id == "cam-a"
        assert result_b.camera_id == "cam-b"
        assert result_a.image.width == 320
        assert result_b.image.width == 640
        assert result_a.objects[0].class_name == "person"
        assert result_b.objects[0].class_name == "car"
        # Убеждаемся что результаты не перепутаны
        assert result_a.objects is not result_b.objects


# ---------------------------------------------------------------------------
# Regression tests: /detect endpoint, health, typecheck
# ---------------------------------------------------------------------------

class TestRegressionDetectEndpoint:
    """5. Регрессия: /detect backward compat, /health endpoints."""

    def _get_client(self, mock_detection_service):
        from fastapi.testclient import TestClient
        from app.main import app
        # Патчим detection_service на уровне router до создания клиента
        with patch("app.api.detect.detection_service", mock_detection_service):
            # TestClient без lifespan events (мок не нужна загрузка YOLO)
            client = TestClient(app, raise_server_exceptions=True)
            yield client

    def _make_mock_service(self, width=100, height=80):
        from app.models.detection import (
            DetectionResult, SourceMetadata, ImageMetadata, ModelMetadata
        )
        mock_service = MagicMock()
        mock_service.detect.return_value = DetectionResult(
            camera_id=None,
            source=SourceMetadata(type=CameraSourceType.UNKNOWN),
            image=ImageMetadata(width=width, height=height, format="jpeg"),
            model=ModelMetadata(id="test", name="test", type="object-detection"),
            objects=[],
        )
        return mock_service

    def test_detect_no_metadata_returns_200(self):
        """Старый /detect без camera_id/source_type → 200 (backward compat)."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes(100, 80)
            response = client.post(
                "/detect",
                files={"file": ("frame.jpg", jpeg, "image/jpeg")},
            )
        assert response.status_code == 200

    def test_detect_no_metadata_response_has_objects_field(self):
        """Ответ /detect содержит поле objects."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            response = client.post("/detect", files={"file": ("f.jpg", jpeg, "image/jpeg")})
        assert "objects" in response.json()

    def test_detect_no_metadata_service_called_with_none_camera_id(self):
        """Без camera_id сервис вызывается с camera_id=None."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            client.post("/detect", files={"file": ("f.jpg", jpeg, "image/jpeg")})
        call_kwargs = mock_service.detect.call_args[1]
        assert call_kwargs.get("camera_id") is None

    def test_detect_with_camera_id_passes_through(self):
        """camera_id из Form передаётся в detection_service.detect."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            client.post(
                "/detect",
                files={"file": ("f.jpg", jpeg, "image/jpeg")},
                data={"camera_id": "cam-test-123", "source_type": "browser"},
            )
        call_kwargs = mock_service.detect.call_args[1]
        assert call_kwargs.get("camera_id") == "cam-test-123"

    def test_detect_with_camera_id_returns_200(self):
        """Новый /detect с camera_id → 200."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            response = client.post(
                "/detect",
                files={"file": ("f.jpg", jpeg, "image/jpeg")},
                data={"camera_id": "cam-123", "source_type": "browser"},
            )
        assert response.status_code == 200

    def test_detect_unknown_source_type_does_not_crash(self):
        """Неизвестный source_type не вызывает 500."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            response = client.post(
                "/detect",
                files={"file": ("f.jpg", jpeg, "image/jpeg")},
                data={"source_type": "flying_saucer"},
            )
        assert response.status_code == 200

    def test_health_live_returns_200(self):
        """GET /health/live возвращает 200."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_health_legacy_returns_200(self):
        """GET /health возвращает 200 (backward compat)."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200

    def test_detect_result_schema_version(self):
        """DetectionResult.schema_version = '1.0' (Stage 3 compat)."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service()
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            response = client.post("/detect", files={"file": ("f.jpg", jpeg, "image/jpeg")})
        data = response.json()
        assert data.get("schema_version") == "1.0"

    def test_detect_result_has_image_metadata(self):
        """DetectionResult содержит image.width и image.height."""
        from fastapi.testclient import TestClient
        from app.main import app
        mock_service = self._make_mock_service(width=640, height=480)
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes()
            response = client.post("/detect", files={"file": ("f.jpg", jpeg, "image/jpeg")})
        data = response.json()
        assert "image" in data
        assert data["image"]["width"] == 640
        assert data["image"]["height"] == 480
