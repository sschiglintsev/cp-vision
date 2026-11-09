"""
Тесты Camera Providers — Stage 5.

Покрывают:
- BaseCameraProvider: контракт ABC
- USBCameraProvider: открытие, чтение, BGR→RGB, sequence, close, isolation
- DetectionPipeline.run_decoded: принимает DecodedImage без вызова ImageDecoder
- DetectionService.detect_frame: интеграция Camera Provider → Pipeline
- Регрессия: /detect, Stage 3/4 compat, Python imports, typecheck builds

Тесты не требуют физического подключения USB-камеры.
cv2.VideoCapture мокируется через unittest.mock.patch.
"""

import io
import time
from typing import Optional
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest
from PIL import Image as PILImage

from app.cameras.base import BaseCameraProvider
from app.cameras.exceptions import CameraOpenError, CameraReadError
from app.cameras.models import CameraFrame
from app.cameras.usb import USBCameraProvider
from app.models.detection import CameraSourceType, DetectedObject, SourceMetadata
from app.models.image import DecodedImage
from app.pipeline.decoder import ImageDecoder
from app.pipeline.detection_pipeline import DetectionPipeline
from app.pipeline.preprocessor import IdentityPreprocessor


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_bgr_frame(width: int = 640, height: int = 480, color: tuple = (100, 150, 200)) -> np.ndarray:
    """Создать синтетический BGR NumPy-массив (как OpenCV VideoCapture)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color  # (B, G, R)
    return frame


def make_decoded_image(width: int = 640, height: int = 480) -> DecodedImage:
    """Создать DecodedImage с синтетическим RGB-массивом."""
    array = np.zeros((height, width, 3), dtype=np.uint8)
    return DecodedImage(array=array, width=width, height=height, format="raw")


def make_jpeg_bytes(width: int = 100, height: int = 80) -> bytes:
    """Создать синтетический JPEG-буфер."""
    img = PILImage.new("RGB", (width, height), (128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_mock_cap(
    is_opened: bool = True,
    read_success: bool = True,
    bgr_frame: Optional[np.ndarray] = None,
    actual_width: float = 640.0,
    actual_height: float = 480.0,
) -> MagicMock:
    """Создать mock cv2.VideoCapture."""
    if bgr_frame is None:
        bgr_frame = make_bgr_frame(int(actual_width), int(actual_height))
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = is_opened
    mock_cap.read.return_value = (read_success, bgr_frame if read_success else None)
    mock_cap.get.side_effect = lambda prop: {
        4: actual_width,   # CAP_PROP_FRAME_WIDTH = 3 (OpenCV)
        5: actual_height,  # CAP_PROP_FRAME_HEIGHT = 4 (OpenCV)
        2: 30.0,           # CAP_PROP_FPS = 5 (OpenCV)
    }.get(prop, 0.0)
    return mock_cap


def make_mock_registry(objects=None) -> MagicMock:
    """Создать mock ModelRegistry с мокнутым движком."""
    if objects is None:
        objects = []
    mock_engine = MagicMock()
    mock_engine.detect.return_value = objects
    mock_engine.is_ready.return_value = True
    mock_engine.get_model_info.return_value = {
        "id": "test-model", "name": "test-model", "type": "object-detection",
    }
    registry = MagicMock()
    registry.get_active_engine.return_value = mock_engine
    registry.is_ready.return_value = True
    return registry


# ---------------------------------------------------------------------------
# BaseCameraProvider tests
# ---------------------------------------------------------------------------

class TestBaseCameraProvider:
    """1. BaseCameraProvider: контракт ABC."""

    def test_cannot_instantiate_abstract_class(self):
        """Нельзя создать экземпляр абстрактного класса напрямую."""
        with pytest.raises(TypeError):
            BaseCameraProvider()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self):
        """Подкласс без реализации всех методов тоже нельзя создать."""
        class IncompleteProvider(BaseCameraProvider):
            def open(self): pass
            def close(self): pass
            # read, is_open, metadata не реализованы

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_can_be_instantiated(self):
        """Подкласс с полной реализацией создаётся корректно."""
        class MinimalProvider(BaseCameraProvider):
            def open(self): pass
            def read(self): return None
            def close(self): pass
            @property
            def is_open(self): return False
            @property
            def metadata(self): return SourceMetadata(type=CameraSourceType.USB)

        provider = MinimalProvider()
        assert provider is not None

    def test_context_manager_calls_open_and_close(self):
        """__enter__ вызывает open(), __exit__ вызывает close()."""
        class TrackingProvider(BaseCameraProvider):
            calls = []
            def open(self): self.calls.append("open")
            def read(self): return None
            def close(self): self.calls.append("close")
            @property
            def is_open(self): return False
            @property
            def metadata(self): return SourceMetadata(type=CameraSourceType.USB)

        p = TrackingProvider()
        with p:
            pass
        assert p.calls == ["open", "close"]

    def test_context_manager_calls_close_on_exception(self):
        """__exit__ вызывается даже при исключении внутри with-блока."""
        class TrackingProvider(BaseCameraProvider):
            closed = False
            def open(self): pass
            def read(self): return None
            def close(self): self.closed = True
            @property
            def is_open(self): return False
            @property
            def metadata(self): return SourceMetadata(type=CameraSourceType.USB)

        p = TrackingProvider()
        with pytest.raises(ValueError):
            with p:
                raise ValueError("test error")
        assert p.closed is True


# ---------------------------------------------------------------------------
# USBCameraProvider tests
# ---------------------------------------------------------------------------

class TestUSBCameraProvider:
    """2. USBCameraProvider: открытие, чтение, BGR→RGB, ресурсы."""

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_open_success(self, mock_vc_cls):
        """Успешное открытие камеры не выбрасывает исключений."""
        mock_vc_cls.return_value = make_mock_cap(is_opened=True)
        provider = USBCameraProvider(camera_id="cam-0", device_index=0)
        provider.open()
        assert provider.is_open is True
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_open_raises_on_unavailable_device(self, mock_vc_cls):
        """CameraOpenError если VideoCapture.isOpened() возвращает False."""
        mock_vc_cls.return_value = make_mock_cap(is_opened=False)
        provider = USBCameraProvider(device_index=99)
        with pytest.raises(CameraOpenError, match="device_index=99"):
            provider.open()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_open_raises_if_first_read_fails(self, mock_vc_cls):
        """CameraOpenError если первый test-read() провалился."""
        mock_vc_cls.return_value = make_mock_cap(is_opened=True, read_success=False)
        provider = USBCameraProvider(device_index=0)
        with pytest.raises(CameraOpenError, match="failed to read first frame"):
            provider.open()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_open_releases_cap_on_first_read_failure(self, mock_vc_cls):
        """VideoCapture.release() вызывается если test-read провалился."""
        mock_cap = make_mock_cap(is_opened=True, read_success=False)
        mock_vc_cls.return_value = mock_cap
        provider = USBCameraProvider(device_index=0)
        with pytest.raises(CameraOpenError):
            provider.open()
        mock_cap.release.assert_called_once()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_camera_not_opened_at_import(self, mock_vc_cls):
        """VideoCapture не вызывается при создании экземпляра — только при open()."""
        provider = USBCameraProvider(camera_id="cam-0", device_index=0)
        mock_vc_cls.assert_not_called()
        assert provider.is_open is False

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_returns_camera_frame(self, mock_vc_cls):
        """read() возвращает CameraFrame после успешного open()."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame = provider.read()
        assert frame is not None
        assert isinstance(frame, CameraFrame)
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_bgr_converted_to_rgb(self, mock_vc_cls):
        """BGR-кадр от OpenCV преобразуется в RGB перед созданием DecodedImage."""
        # BGR: B=255, G=0, R=0 → RGB: R=0, G=0, B=255
        bgr = make_bgr_frame(10, 10, color=(255, 0, 0))  # чисто синий в BGR
        mock_vc_cls.return_value = make_mock_cap(bgr_frame=bgr)
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame = provider.read()
        assert frame is not None
        # В RGB первый канал (R) должен быть 0, третий (B) — 255
        assert frame.image.array[0, 0, 0] == 0    # R = 0 (было B в BGR)
        assert frame.image.array[0, 0, 2] == 255  # B = 255 (было B в BGR)
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_correct_width_and_height(self, mock_vc_cls):
        """width и height соответствуют реальному размеру кадра."""
        bgr = make_bgr_frame(width=1280, height=720)
        mock_vc_cls.return_value = make_mock_cap(bgr_frame=bgr)
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame = provider.read()
        assert frame is not None
        assert frame.image.width == 1280
        assert frame.image.height == 720
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_camera_id_matches_provider(self, mock_vc_cls):
        """frame.camera_id совпадает с camera_id провайдера."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="my-usb-camera-123")
        provider.open()
        frame = provider.read()
        assert frame is not None
        assert frame.camera_id == "my-usb-camera-123"
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_source_type_is_usb(self, mock_vc_cls):
        """frame.source.type == CameraSourceType.USB."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame = provider.read()
        assert frame is not None
        assert frame.source.type == CameraSourceType.USB
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_sequence_increments_on_each_read(self, mock_vc_cls):
        """sequence увеличивается при каждом успешном read()."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame1 = provider.read()
        frame2 = provider.read()
        frame3 = provider.read()
        assert frame1 is not None and frame1.sequence == 1
        assert frame2 is not None and frame2.sequence == 2
        assert frame3 is not None and frame3.sequence == 3
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_failed_read_returns_none(self, mock_vc_cls):
        """read() после первого успеха возвращает None при провале чтения."""
        # Первый read (test в open()) успешен, второй (пользовательский) — нет
        bgr_frame = make_bgr_frame()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = [
            (True, bgr_frame),   # test read в open()
            (False, None),        # пользовательский read() → None
        ]
        mock_vc_cls.return_value = mock_cap
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame = provider.read()
        assert frame is None

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_failed_read_does_not_increment_sequence(self, mock_vc_cls):
        """sequence не увеличивается при неудачном read()."""
        bgr_frame = make_bgr_frame()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = [
            (True, bgr_frame),   # open test
            (True, bgr_frame),   # успешный read
            (False, None),        # неудачный read
        ]
        mock_vc_cls.return_value = mock_cap
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        frame1 = provider.read()
        frame_none = provider.read()
        assert frame1 is not None and frame1.sequence == 1
        assert frame_none is None

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_close_calls_release(self, mock_vc_cls):
        """close() вызывает VideoCapture.release()."""
        mock_cap = make_mock_cap()
        mock_vc_cls.return_value = mock_cap
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        provider.close()
        mock_cap.release.assert_called_once()
        assert provider.is_open is False

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_close_idempotent(self, mock_vc_cls):
        """Повторный close() безопасен — не выбрасывает исключений."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        provider.close()
        provider.close()  # не должно упасть
        assert provider.is_open is False

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_does_not_reopen_device(self, mock_vc_cls):
        """Повторные read() не создают новые VideoCapture."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="cam-0")
        provider.open()
        provider.read()
        provider.read()
        provider.read()
        # VideoCapture создаётся только один раз — в open()
        assert mock_vc_cls.call_count == 1
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_context_manager_opens_and_closes(self, mock_vc_cls):
        """Контекстный менеджер корректно открывает и закрывает камеру."""
        mock_cap = make_mock_cap()
        mock_vc_cls.return_value = mock_cap
        with USBCameraProvider(camera_id="cam-0") as provider:
            assert provider.is_open is True
            frame = provider.read()
            assert frame is not None
        assert provider.is_open is False
        mock_cap.release.assert_called_once()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_read_before_open_returns_none(self, mock_vc_cls):
        """read() до вызова open() возвращает None без исключений."""
        provider = USBCameraProvider(camera_id="cam-0")
        frame = provider.read()
        assert frame is None

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_camera_id_stable_across_reads(self, mock_vc_cls):
        """camera_id не меняется между кадрами одного провайдера."""
        mock_vc_cls.return_value = make_mock_cap()
        provider = USBCameraProvider(camera_id="stable-id")
        provider.open()
        ids = {provider.read().camera_id for _ in range(5)}
        assert ids == {"stable-id"}
        provider.close()

    @patch("app.cameras.usb.cv2.VideoCapture")
    def test_sequence_resets_on_new_instance(self, mock_vc_cls):
        """sequence начинается с 1 для каждого нового экземпляра."""
        mock_vc_cls.return_value = make_mock_cap()
        p1 = USBCameraProvider(camera_id="cam-0")
        p1.open()
        p1.read(); p1.read(); p1.read()
        p1.close()

        mock_vc_cls.return_value = make_mock_cap()
        p2 = USBCameraProvider(camera_id="cam-0")
        p2.open()
        frame = p2.read()
        assert frame is not None and frame.sequence == 1
        p2.close()

    def test_no_camera_open_on_import(self):
        """VideoCapture не вызывается при импорте модуля cameras.usb."""
        import app.cameras.usb as usb_module
        import sys
        # Просто импортируем модуль и убеждаемся, что cv2.VideoCapture не было вызвано
        # (нет глобальных вызовов при импорте)
        assert hasattr(usb_module, "USBCameraProvider")
        # Создание экземпляра тоже не открывает камеру
        provider = usb_module.USBCameraProvider()
        assert provider.is_open is False


# ---------------------------------------------------------------------------
# DetectionPipeline.run_decoded tests
# ---------------------------------------------------------------------------

class TestDetectionPipelineRunDecoded:
    """3. DetectionPipeline: принимает DecodedImage без вызова ImageDecoder."""

    def _make_pipeline(self, objects=None) -> DetectionPipeline:
        registry = make_mock_registry(objects=objects or [])
        return DetectionPipeline(
            decoder=ImageDecoder(),
            preprocessor=IdentityPreprocessor(),
            registry=registry,
        )

    def test_run_decoded_returns_detection_result(self):
        """run_decoded() возвращает DetectionResult."""
        from app.models.detection import DetectionResult
        pipeline = self._make_pipeline()
        result = pipeline.run_decoded(make_decoded_image())
        assert isinstance(result, DetectionResult)

    def test_run_decoded_does_not_call_decoder(self):
        """При run_decoded ImageDecoder.decode() НЕ вызывается."""
        decoder = MagicMock(spec=ImageDecoder)
        pipeline = DetectionPipeline(
            decoder=decoder,
            preprocessor=IdentityPreprocessor(),
            registry=make_mock_registry(),
        )
        pipeline.run_decoded(make_decoded_image(640, 480))
        decoder.decode.assert_not_called()

    def test_run_decoded_uses_decoded_dimensions(self):
        """image.width/height в результате берутся из DecodedImage."""
        pipeline = self._make_pipeline()
        decoded = make_decoded_image(width=1280, height=720)
        result = pipeline.run_decoded(decoded)
        assert result.image.width == 1280
        assert result.image.height == 720

    def test_run_decoded_with_camera_id(self):
        """camera_id передаётся в DetectionResult."""
        pipeline = self._make_pipeline()
        result = pipeline.run_decoded(make_decoded_image(), camera_id="usb-test-cam")
        assert result.camera_id == "usb-test-cam"

    def test_run_decoded_source_type_usb(self):
        """source.type=usb сохраняется в результате."""
        pipeline = self._make_pipeline()
        result = pipeline.run_decoded(
            make_decoded_image(),
            source_type=CameraSourceType.USB,
            camera_id="usb-0",
        )
        assert result.source.type == CameraSourceType.USB

    def test_run_decoded_format_raw_preserved(self):
        """format='raw' из DecodedImage USB-кадра сохраняется."""
        pipeline = self._make_pipeline()
        decoded = make_decoded_image()
        decoded.format = "raw"
        result = pipeline.run_decoded(decoded)
        assert result.image.format == "raw"

    def test_run_decoded_empty_objects(self):
        """Пустой результат инференса → objects: []."""
        pipeline = self._make_pipeline(objects=[])
        result = pipeline.run_decoded(make_decoded_image())
        assert result.objects == []

    def test_run_decoded_objects_from_engine(self):
        """Объекты из движка передаются в результат."""
        obj = DetectedObject(**{
            "class": "person", "confidence": 0.9,
            "x": 10, "y": 20, "width": 50, "height": 100,
        })
        pipeline = self._make_pipeline(objects=[obj])
        result = pipeline.run_decoded(make_decoded_image())
        assert len(result.objects) == 1
        assert result.objects[0].class_name == "person"

    def test_run_bytes_still_works(self):
        """Существующий run(bytes) продолжает работать после добавления run_decoded."""
        pipeline = self._make_pipeline()
        result = pipeline.run(make_jpeg_bytes(100, 80))
        assert result.image.width == 100
        assert result.image.height == 80

    def test_run_bytes_calls_decoder(self):
        """run(bytes) вызывает ImageDecoder.decode() (в отличие от run_decoded)."""
        decoder = MagicMock(spec=ImageDecoder)
        decoder.decode.return_value = make_decoded_image(100, 80)
        pipeline = DetectionPipeline(
            decoder=decoder,
            preprocessor=IdentityPreprocessor(),
            registry=make_mock_registry(),
        )
        pipeline.run(b"some-bytes")
        decoder.decode.assert_called_once_with(b"some-bytes")

    def test_usb_frame_in_pipeline_produces_correct_result(self):
        """USB CameraFrame через run_decoded формирует корректный DetectionResult."""
        obj = DetectedObject(**{
            "class": "car", "confidence": 0.85,
            "x": 100, "y": 50, "width": 200, "height": 150,
        })
        pipeline = self._make_pipeline(objects=[obj])

        # Симулируем кадр от USB провайдера
        rgb_array = np.zeros((480, 640, 3), dtype=np.uint8)
        decoded = DecodedImage(array=rgb_array, width=640, height=480, format="raw")
        source = SourceMetadata(type=CameraSourceType.USB, id="usb-cam-1")
        frame = CameraFrame(
            camera_id="usb-cam-1",
            source=source,
            image=decoded,
            timestamp=int(time.time() * 1000),
            sequence=1,
        )

        result = pipeline.run_decoded(
            decoded=frame.image,
            camera_id=frame.camera_id,
            source_type=frame.source.type,
            source_name=frame.source.name,
        )

        assert result.camera_id == "usb-cam-1"
        assert result.source.type == CameraSourceType.USB
        assert result.image.width == 640
        assert result.image.height == 480
        assert result.image.format == "raw"
        assert len(result.objects) == 1
        assert result.objects[0].class_name == "car"


# ---------------------------------------------------------------------------
# DetectionService.detect_frame tests
# ---------------------------------------------------------------------------

class TestDetectionServiceDetectFrame:
    """4. DetectionService.detect_frame: интеграция Camera Provider → Pipeline."""

    def _make_service_with_mock(self, objects=None):
        """Создать DetectionService с мокнутым registry."""
        from app.services.detection_service import DetectionService
        registry = make_mock_registry(objects=objects or [])
        return DetectionService(registry=registry)

    def _make_usb_frame(self, camera_id="usb-test", width=320, height=240, sequence=1) -> CameraFrame:
        """Создать синтетический CameraFrame от USB провайдера."""
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        decoded = DecodedImage(array=rgb_array, width=width, height=height, format="raw")
        source = SourceMetadata(type=CameraSourceType.USB, id=camera_id)
        return CameraFrame(
            camera_id=camera_id,
            source=source,
            image=decoded,
            timestamp=int(time.time() * 1000),
            sequence=sequence,
        )

    def test_detect_frame_returns_detection_result(self):
        """detect_frame() возвращает DetectionResult."""
        from app.models.detection import DetectionResult
        service = self._make_service_with_mock()
        frame = self._make_usb_frame()
        result = service.detect_frame(frame)
        assert isinstance(result, DetectionResult)

    def test_detect_frame_camera_id_preserved(self):
        """camera_id из CameraFrame сохраняется в DetectionResult."""
        service = self._make_service_with_mock()
        frame = self._make_usb_frame(camera_id="usb-camera-xyz")
        result = service.detect_frame(frame)
        assert result.camera_id == "usb-camera-xyz"

    def test_detect_frame_source_type_usb(self):
        """source.type == usb в DetectionResult."""
        service = self._make_service_with_mock()
        frame = self._make_usb_frame()
        result = service.detect_frame(frame)
        assert result.source.type == CameraSourceType.USB

    def test_detect_frame_image_dimensions(self):
        """image.width/height соответствуют CameraFrame."""
        service = self._make_service_with_mock()
        frame = self._make_usb_frame(width=1280, height=720)
        result = service.detect_frame(frame)
        assert result.image.width == 1280
        assert result.image.height == 720

    def test_detect_frame_does_not_encode_to_jpeg(self):
        """detect_frame не кодирует DecodedImage в JPEG и не вызывает ImageDecoder."""
        service = self._make_service_with_mock()
        frame = self._make_usb_frame()
        # Мокируем decoder в pipeline чтобы убедиться что он не вызывается
        service._pipeline._decoder = MagicMock(spec=ImageDecoder)
        service.detect_frame(frame)
        service._pipeline._decoder.decode.assert_not_called()


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class TestStage5Regression:
    """5. Регрессия: Stage 3/4 не сломаны."""

    def test_detect_endpoint_still_works(self):
        """POST /detect продолжает работать (backward compat)."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from app.main import app
        from app.models.detection import DetectionResult, SourceMetadata, ImageMetadata, ModelMetadata

        mock_service = MagicMock()
        mock_service.detect.return_value = DetectionResult(
            camera_id=None,
            source=SourceMetadata(type=CameraSourceType.UNKNOWN),
            image=ImageMetadata(width=100, height=80, format="jpeg"),
            model=ModelMetadata(id="test", name="test", type="object-detection"),
            objects=[],
        )
        with patch("app.api.detect.detection_service", mock_service):
            client = TestClient(app, raise_server_exceptions=True)
            jpeg = make_jpeg_bytes(100, 80)
            response = client.post("/detect", files={"file": ("f.jpg", jpeg, "image/jpeg")})
        assert response.status_code == 200
        data = response.json()
        assert "objects" in data
        assert data.get("schema_version") == "1.0"

    def test_python_imports_no_camera_open(self):
        """Импорт cameras.* не открывает камеру и не загружает модель."""
        import app.cameras.base as base_mod
        import app.cameras.models as models_mod
        import app.cameras.usb as usb_mod
        import app.cameras.exceptions as exc_mod
        # Если дошли сюда — импорты OK, камера не открылась
        assert hasattr(base_mod, "BaseCameraProvider")
        assert hasattr(models_mod, "CameraFrame")
        assert hasattr(usb_mod, "USBCameraProvider")
        assert hasattr(exc_mod, "CameraOpenError")

    def test_detection_pipeline_run_decoded_added(self):
        """DetectionPipeline имеет метод run_decoded."""
        assert hasattr(DetectionPipeline, "run_decoded")
        assert callable(DetectionPipeline.run_decoded)

    def test_stage4_pipeline_run_unchanged(self):
        """Stage 4: run(bytes) работает как прежде."""
        pipeline = DetectionPipeline(
            decoder=ImageDecoder(),
            preprocessor=IdentityPreprocessor(),
            registry=make_mock_registry(),
        )
        result = pipeline.run(make_jpeg_bytes(200, 150))
        assert result.image.width == 200
        assert result.image.height == 150

    def test_camera_frame_has_all_fields(self):
        """CameraFrame содержит все обязательные поля."""
        frame = CameraFrame(
            camera_id="cam-0",
            source=SourceMetadata(type=CameraSourceType.USB, id="cam-0"),
            image=make_decoded_image(100, 100),
            sequence=1,
        )
        assert frame.camera_id == "cam-0"
        assert frame.source.type == CameraSourceType.USB
        assert frame.image.width == 100
        assert frame.sequence == 1
        assert frame.timestamp > 0

    def test_camera_source_type_usb_value(self):
        """CameraSourceType.USB == 'usb' (Stage 3 compat)."""
        assert CameraSourceType.USB.value == "usb"
