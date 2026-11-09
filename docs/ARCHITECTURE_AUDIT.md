# CP Vision — Architecture Audit

**Дата аудита:** 7 ноября 2026  
**Версия проекта:** 0.3.0 (Stage 3 — Universal Detection Result)  
**Stage 1 выполнен:** 7 ноября 2026  
**Stage 2 выполнен:** 7 ноября 2026  
**Stage 3 выполнен:** 7 ноября 2026  
**Аудитор:** AI Agent (на основе полного анализа кода)

---

## 1. Текущая архитектура (фактическая)

### Схема потока данных

```
Browser (getUserMedia)
  │  { frame: base64 JPEG, cameraId: string | null }, 200 мс интервал
  ↓ Socket.IO  camera:frame
Backend :3000  (Node.js + Express + Socket.IO)
  │  multipart/form-data: file + camera_id + source_type
  ↓ axios  POST /detect
CV Service :8000  (Python + FastAPI + YOLOv11n)
  │  DetectionResult { schema_version, camera_id, source, image, model, objects, timestamp }
  ↓ HTTP response
Backend
  │  { objects, error, timestamp, cameraId, source, image, model }
  ↓ Socket.IO  detection:frame
Browser (Canvas overlay)
```

### Ключевые параметры

| Параметр | Значение |
|---|---|
| Формат кадра | JPEG base64, качество 0.8 |
| Разрешение кадра | 1280×720 (ideal) |
| Размер кадра | ~80–120 KB |
| Интервал отправки | 200 мс |
| Backpressure | `isProcessing` per socket |
| Sticky TTL | 600 мс (frontend) |
| Модель | YOLOv11n (5.4 МБ, 80 классов) |
| Таймаут HTTP к CV Service | 10 сек |
| Максимальный размер WS буфера | 5 МБ |

### Файловая структура (источники истины)

```
cp-vision/
├── frontend/src/
│   ├── api/client.ts               — axios + interceptor refresh
│   ├── api/authApi.ts              — auth HTTP endpoints
│   ├── components/
│   │   ├── AuthInitializer/        — silent refresh при перезагрузке
│   │   ├── CameraOverlay/          — canvas bounding boxes
│   │   └── PrivateRoute/           — защита маршрутов
│   ├── hooks/
│   │   ├── useCamera.ts            — getUserMedia, захват кадра
│   │   ├── useCameraDetection.ts   — отправка кадров, sticky TTL
│   │   └── useSocket.ts            — Socket.IO подключение
│   ├── pages/
│   │   ├── LoginPage.tsx           — вход + регистрация
│   │   ├── DashboardPage.tsx       — приветствие, кнопка на камеру
│   │   └── CameraPage.tsx          — основная страница
│   ├── store/authStore.ts          — in-memory: access token + user
│   └── types/
│       ├── auth.ts                 — DTO типы авторизации
│       └── detection.ts            — CameraSourceType, SourceMetadata, ImageMetadata, ModelMetadata, DetectionResult, DetectedObject
│
├── backend/src/
│   ├── websocket/socketEvents.ts   — camera:frame (string|{frame,cameraId}) → detection:frame (enriched)
│   ├── services/CvServiceClient.ts — detectBuffer(buffer, DetectBufferOptions) → CvDetectionResult
│   ├── types/detection.ts          — CvDetectionResult, DetectedObjectDto и DTO-типы
│   ├── controllers/AuthController.ts
│   ├── services/AuthService.ts
│   ├── repositories/
│   │   ├── UserRepository.ts
│   │   ├── DetectionRepository.ts       ← не используется в runtime
│   │   └── DetectionResultRepository.ts ← не используется в runtime
│   └── middleware/auth.ts, errorHandler.ts, validate.ts
│
└── cv-service/app/
    ├── api/
    │   ├── detect.py               — POST /detect (file + optional camera_id, source_type, source_name)
    │   └── health.py               — /health/live, /health/ready, /health
    ├── core/
    │   └── config.py               — Settings (pydantic-settings)
    ├── inference/
    │   ├── base.py                 — BaseInferenceEngine (ABC)
    │   ├── yolo_engine.py          — YoloEngine(BaseInferenceEngine)
    │   └── registry.py             — ModelRegistry + singleton
    ├── models/
    │   └── detection.py            — CameraSourceType, SourceMetadata, ImageMetadata, ModelMetadata, DetectionResult, DetectedObject
    ├── services/
    │   └── detection_service.py    — DetectionService → BaseInferenceEngine → DetectionResult
    └── main.py                     — lifespan (инициализация engine)
```

---

## 2. Что реализовано правильно

### Backend
- ✅ Backpressure через `isProcessing` per socket — кадры не накапливаются в очереди
- ✅ Персональные комнаты Socket.IO `user:<id>` — изоляция событий между пользователями
- ✅ JWT верификация при WebSocket handshake
- ✅ Централизованный `errorHandler` middleware
- ✅ Zod-валидация auth endpoints
- ✅ Refresh token в HttpOnly cookie (30 дней)
- ✅ Axios interceptor для автоматического обновления access token при 401
- ✅ Защита `/auth/refresh` от рекурсивного перехвата interceptor

### CV Service
- ✅ Модель загружается **один раз** при старте (`detection_service = YoloDetectionService()` на уровне модуля)
- ✅ Pydantic-валидация входных и выходных данных
- ✅ Настройки через `pydantic-settings` — всё конфигурируется через `.env`
- ✅ `/health` endpoint

### Frontend
- ✅ Sticky TTL 600 мс — предотвращает мигание bounding boxes при пропуске кадра
- ✅ Правильный захват кадра из `<video>` через canvas
- ✅ Выбор камеры через `enumerateDevices`
- ✅ Индикатор статуса WebSocket соединения
- ✅ Обработка ошибки `NotAllowedError` при запросе доступа к камере
- ✅ `PrivateRoute` — защита маршрутов без хранения токена в localStorage
- ✅ `AuthInitializer` — сессия восстанавливается при перезагрузке страницы

---

## 3. Архитектурные ограничения и проблемы

### 🔴 Критические

#### ~~CV-1: Нет абстракции Inference Engine~~ ✅ Реализовано (Stage 2)

~~`YoloDetectionService` не реализует никакого протокола/ABC.~~  
Реализовано: `BaseInferenceEngine` ABC → `YoloEngine` → `ModelRegistry` → `DetectionService`. `detect.py` по-прежнему импортирует `detection_service`, но тот работает через интерфейс, не напрямую через YOLO.

#### ~~CV-2: Нет размеров исходного изображения в ответе~~ ✅ Реализовано (Stage 3)

~~CV Service возвращал координаты без размеров исходного изображения.~~  
Реализовано: `DetectionResult` содержит `image: { width, height, format }` — реальные размеры читаются через `PIL.Image.open()` независимо от инференса. Frontend получает размеры в `detection:frame`.

#### ~~FE-1: `useSocket` возвращает устаревший ref~~ ✅ Исправлено (Stage 1)

~~`socketRef.current` равен `null` в момент первого рендера.~~  
Исправлено: socket возвращается через `useState`, компоненты получают реальный instance сразу после коннекта.

### 🟡 Существенные

#### ~~BE-1: Ошибка детекции неотличима от пустого кадра~~ ✅ Исправлено (Stage 1)

~~Если CV Service упал — frontend получал `{ objects: [] }` и молча очищал bounding boxes.~~  
Исправлено: `detection:frame` теперь отправляет `{ objects, error, timestamp }`. При ошибке `error` содержит строку, frontend показывает `Alert`.

#### BE-2: Мёртвый код — частично исправлено (Stage 1)

- ~~`CvServiceClient.detect(file: Express.Multer.File)`~~ ✅ Удалён
- `DetectionRepository`, `DetectionResultRepository` — по-прежнему существуют, зарезервированы для истории детекций (не удалять)

#### ~~CV-3: Несоответствие дефолта конфига~~ ✅ Исправлено (Stage 1)

~~`yolo_model: str = "yolov8n.pt"` — при отсутствии `.env` загружался устаревший YOLOv8.~~  
Исправлено: дефолт изменён на `"yolo11n.pt"`.

#### ~~CV-4: Deprecated FastAPI lifecycle~~ ✅ Исправлено (Stage 1)

~~`@app.on_event("startup")` — устарел с FastAPI 0.93.~~  
Исправлено: используется `@asynccontextmanager lifespan`.

#### ~~CV-5: `/health` не проверяет состояние модели~~ ✅ Исправлено (Stage 1)

~~Возвращал `ok` даже если YOLO не загружена.~~  
Исправлено: добавлены `GET /health/live` (liveness) и `GET /health/ready` (readiness, 503 если модель не готова). `GET /health` сохранён для обратной совместимости.

#### ~~FE-2: `captureFrame` создаёт новый canvas каждые 200 мс~~ ✅ Исправлено (Stage 1)

~~5 аллокаций DOM-элементов в секунду.~~  
Исправлено: `captureCanvasRef` — один переиспользуемый canvas, обновляет размер только при смене разрешения.

#### ~~FE-3: `CameraOverlay` не реагирует на resize независимо~~ ✅ Исправлено (Stage 1)

~~Масштаб пересчитывался только при изменении `objects`.~~  
Исправлено: добавлен независимый `window.addEventListener('resize', handleResize)`.

### 🟢 Незначительные

- ~~CORS origin `'http://localhost:5173'` захардкожен в двух местах~~ ✅ Исправлено (Stage 1) — вынесен в `CORS_ORIGIN` env-переменную
- ~~`config.py` находится в `utils/`~~ ✅ Исправлено (Stage 2) — перенесён в `core/config.py`
- `__init__.py` файлы пустые и не несут смысловой нагрузки
- `Detection.fileName` в схеме БД — поле из эпохи загрузки файлов, бессмысленно для стриминга
- ~~В ответе нет `model.id` — frontend не знает какая модель делала детекцию~~ ✅ Реализовано (Stage 3) — `detection:frame` содержит `model: { id, name, type }`

---

## 4. Что необходимо изменить

Приоритизированный список:

| # | Изменение | Сервис | Риск | Статус |
|---|---|---|---|---|
| 1 | `useSocket` — исправить возврат socket через state | Frontend | Нулевой | ✅ Stage 1 |
| 2 | Различать ошибку и пустой кадр в `detection:frame` | Backend + Frontend | Низкий (additive) | ✅ Stage 1 |
| 3 | Выровнять дефолт модели в `config.py` | CV Service | Нулевой | ✅ Stage 1 |
| 4 | Удалить мёртвый метод `detect(file)` | Backend | Нулевой | ✅ Stage 1 |
| 5 | CORS origin → env-переменная | Backend | Нулевой | ✅ Stage 1 |
| 6 | `BaseInferenceEngine` ABC интерфейс | CV Service | Нулевой (additive) | ✅ Stage 2 |
| 7 | `YoloEngine` реализует `BaseInferenceEngine` | CV Service | Нулевой | ✅ Stage 2 |
| 8 | `ModelRegistry` — загрузка и получение по id | CV Service | Нулевой | ✅ Stage 2 |
| 9 | Добавить `image.width/height` в ответ CV Service | CV + Backend + Frontend | Низкий (additive) | ✅ Stage 3 |
| 10 | `BaseCameraProvider` интерфейс (заглушка) | CV Service | Нулевой (additive) | ⬜ Stage 4 |
| 11 | `lifespan` вместо `on_event` | CV Service | Нулевой | ✅ Stage 1 |
| 12 | `/health` проверяет состояние модели | CV Service | Нулевой | ✅ Stage 1 |
| 13 | Расширенный формат Detection Result | Все | Низкий (additive) | ✅ Stage 3 |

---

## 5. Изменения, нарушающие обратную совместимость

### ✅ Обратно совместимые (additive)

- Добавление новых полей в `detection:frame` — `{ objects, error?, image?, model? }`. Frontend читает `objects` и продолжает работать.
- Добавление `image.width/height` в ответ CV Service — Backend проксирует, Frontend может игнорировать.
- Создание `BaseInferenceEngine`, `ModelRegistry`, `BaseCameraProvider` — новые файлы, не меняют существующие.

### ⚠️ Требуют согласованного обновления

- Изменение структуры `objects[]` (например, `x/y/width/height` → `bbox.x/bbox.y`) — сломает `CameraOverlay`. Нужен адаптер или постепенная миграция с поддержкой обоих форматов.

### 🔴 Несовместимые (не делать)

- Переименование Socket.IO событий `camera:frame` / `detection:frame`.
- Удаление полей из `DetectedObject`.
- Изменение структуры auth endpoints.

---

## 6. Предлагаемая архитектура v2

### CV Service

```
cv-service/app/
├── core/
│   └── config.py               # настройки (перенести из utils/)
├── inference/
│   ├── __init__.py
│   ├── base.py                 # BaseInferenceEngine (ABC)
│   ├── yolo_engine.py          # YoloEngine(BaseInferenceEngine)
│   └── registry.py             # ModelRegistry
├── cameras/
│   ├── __init__.py
│   ├── base.py                 # BaseCameraProvider (ABC)
│   └── browser_camera.py       # BrowserCameraProvider (концепция)
├── pipeline/
│   ├── __init__.py
│   └── detection_pipeline.py   # preprocess → infer → postprocess
├── models/
│   └── detection.py            # Pydantic: расширенный DetectionResponse
├── api/
│   ├── detect.py               # POST /detect — через registry
│   └── health.py               # GET /health — с проверкой модели
└── main.py                     # lifespan, инициализация registry
```

### Backend

```
backend/src/
├── websocket/
│   ├── socketEvents.ts         # connection management (упростить)
│   └── cameraHandler.ts        # camera:frame логика (выделить)
└── services/
    └── CvServiceClient.ts      # удалить мёртвый detect(file)
```

### Frontend

```
frontend/src/
├── hooks/
│   ├── useSocket.ts            # исправить: socket через useState
│   └── useCameraDetection.ts   # разделить error и empty result
├── types/
│   └── detection.ts            # расширить: image, model, error
└── components/
    └── CameraOverlay/          # исправить: resize listener
```

### Расширенный формат Detection Result v2

```typescript
// Обратно совместимо — objects остаётся на том же уровне
interface DetectionFrame {
  objects: DetectedObject[];        // ← сохранён текущий контракт
  error?: string;                   // новое: описание ошибки детекции
  image?: {                         // новое: размеры исходного кадра
    width: number;
    height: number;
  };
  model?: {                         // новое: информация о модели
    id: string;
    type: 'object_detection' | 'classification' | 'segmentation';
  };
  timestamp?: number;               // новое: unix ms
}
```

### BaseInferenceEngine (Python)

```python
# inference/base.py
from abc import ABC, abstractmethod
from app.models.detection import DetectionResponse

class BaseInferenceEngine(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def detect(self, image_bytes: bytes) -> DetectionResponse: ...

    @abstractmethod
    def get_model_info(self) -> dict[str, str]: ...

    @abstractmethod
    def shutdown(self) -> None: ...

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...
```

### BaseCameraProvider (Python)

```python
# cameras/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class CameraStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class CameraConfig:
    camera_id: str
    width: int = 1280
    height: int = 720
    fps: int = 30

class BaseCameraProvider(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def read_frame(self) -> bytes | None: ...

    @abstractmethod
    async def reconnect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    def get_status(self) -> CameraStatus: ...
```

---

## 7. План миграции по этапам

### ✅ Этап 1 — Быстрые исправления (выполнен 7 ноября 2026)

**Цель:** устранить существующие баги и несоответствия, не трогая архитектуру.

| Задача | Файл | Статус |
|---|---|---|
| Исправить `useSocket` — socket через useState | `hooks/useSocket.ts` | ✅ |
| Разделить ошибку и пустой кадр в `detection:frame` | `websocket/socketEvents.ts` + `useCameraDetection.ts` | ✅ |
| Выровнять дефолт модели в config.py | `cv-service/app/utils/config.py` | ✅ |
| Удалить мёртвый `detect(file)` из CvServiceClient | `services/CvServiceClient.ts` | ✅ |
| CORS origin в env | `app.ts`, `socketEvents.ts`, `config/env.ts` | ✅ |
| `lifespan` вместо `on_event` | `cv-service/app/main.py` | ✅ |
| Liveness / Readiness endpoints | `cv-service/app/main.py` | ✅ |
| Переиспользование canvas в `captureFrame` | `hooks/useCamera.ts` | ✅ |
| Resize listener в `CameraOverlay` | `components/CameraOverlay/CameraOverlay.tsx` | ✅ |

**Проверки пройдены:** `tsc --noEmit` ✅ · `vite build` ✅ · FastAPI startup ✅ · `/health/ready` → `{"status":"ready","model":"yolo11n.pt"}` ✅

---

### Этап 2 — Inference Engine абстракция (CV Service)

**Цель:** изолировать YOLO за интерфейсом, подготовить к замене модели.

| Задача | Файл | Статус |
|---|---|---|
| `BaseInferenceEngine` ABC | `inference/base.py` | ✅ |
| `YoloEngine(BaseInferenceEngine)` | `inference/yolo_engine.py` | ✅ |
| `ModelRegistry` | `inference/registry.py` | ✅ |
| `config.py` → `core/config.py` | переместить | ✅ |
| `main.py` lifespan + инициализация engine | `main.py` | ✅ |
| `/health/ready` проверяет `registry.is_ready()` | `api/health.py` | ✅ |
| Устранить import-time загрузку модели | `main.py`, `detection_service.py` | ✅ |
| ~~Добавить `image.width/height` в ответ~~ | — | ✅ Реализовано в Stage 3 |

**Проверки пройдены:** `POST /detect` → тот же формат ✅ · `GET /health/ready` → `{"status":"ready","model":"yolo11n.pt"}` ✅ · модель загружается один раз ✅ · обратная совместимость ✅

---

### ✅ Этап 3 — Universal Detection Result (выполнен 7 ноября 2026)

**Цель:** создать универсальный формат результата детекции, сквозной через весь pipeline.

| Задача | Файл | Статус |
|---|---|---|
| `DetectionResult` + `CameraSourceType`, `SourceMetadata`, `ImageMetadata`, `ModelMetadata` | `cv-service/app/models/detection.py` | ✅ |
| `DetectionService.detect()` принимает metadata, строит `DetectionResult` | `cv-service/app/services/detection_service.py` | ✅ |
| `get_model_info()` возвращает `id` движка | `cv-service/app/inference/yolo_engine.py` | ✅ |
| Optional Form-поля `camera_id`, `source_type`, `source_name` в `/detect` | `cv-service/app/api/detect.py` | ✅ |
| DTO-типы `CvDetectionResult`, `SourceMetadataDto`, `ImageMetadataDto`, `ModelMetadataDto` | `backend/src/types/detection.ts` | ✅ |
| `detectBuffer` принимает `DetectBufferOptions`, возвращает `CvDetectionResult` | `backend/src/services/CvServiceClient.ts` | ✅ |
| `camera:frame` принимает `string \| {frame, cameraId}`, `detection:frame` обогащён | `backend/src/websocket/socketEvents.ts` | ✅ |
| TypeScript типы `DetectionResult`, `SourceMetadata`, `ImageMetadata`, `ModelMetadata` | `frontend/src/types/detection.ts` | ✅ |
| `useCameraDetection` принимает `cameraId`, emit как объект | `frontend/src/hooks/useCameraDetection.ts` | ✅ |
| Передаёт `activeDeviceId` как `cameraId` | `frontend/src/pages/CameraPage.tsx` | ✅ |

**Проверки пройдены:** Python-импорты без загрузки модели ✅ · Старый `/detect` без метаданных → `camera_id=null, type=unknown` ✅ · Новый `/detect` с metadata → отражается в ответе ✅ · `model.id=yolo11n` ✅ · Backend `tsc --noEmit` ✅ · Frontend `vite build` ✅

---

### Этап 4 — Camera Provider интерфейс (CV Service)

**Цель:** формализовать интерфейс для будущих источников видео.

| Задача | Файл |
|---|---|
| `BaseCameraProvider` ABC | `cameras/base.py` |
| `BrowserCameraProvider` заглушка | `cameras/browser_camera.py` |
| `CameraRegistry` | `cameras/registry.py` |

Browser camera workflow при этом не меняется — она продолжает работать через WebSocket как сейчас.

**Проверка:** существующий pipeline работает без изменений.

---

### Этап 5 — Detection Pipeline (CV Service)

**Цель:** выделить preprocessing/postprocessing как отдельный слой, устранить двойной decode изображения.

```
image_bytes
  → preprocess(image_bytes) → ndarray + ImageMetadata
  → engine.infer(ndarray)   → raw_results
  → postprocess(raw_results, image_size) → List[DetectedObject]
  → DetectionService builds DetectionResult
```

Это устраняет текущий технический долг (двойной `PIL.Image.open` в `DetectionService` и `YoloEngine`) и открывает точки для: object tracking, pose estimation, segmentation.

---

### Этап 6 — Использование `image` из `detection:frame` в Frontend

**Цель:** масштабировать bounding boxes по реальным размерам кадра из ответа сервера.

| Задача | Файл |
|---|---|
| `CameraOverlay` читает `image.width/height` из payload | `components/CameraOverlay/CameraOverlay.tsx` |
| Передать `image` из `detection:frame` в `CameraOverlay` | `pages/CameraPage.tsx`, `hooks/useCameraDetection.ts` |

---

## 8. Текущие технические ограничения

| Ограничение | Описание | Когда актуально |
|---|---|---|
| Только browser camera | Нет USB, RTSP, IP камер | При промышленном применении |
| Одна модель на сервис | Нет выбора модели в runtime | При мультимодельной детекции |
| Нет tracking | Объекты не имеют stableId между кадрами | При трекинге |
| Нет истории | Результаты не сохраняются в БД | При аналитике |
| Нет фильтрации классов | Frontend показывает все 80 классов | При фокусировке на конкретных объектах |
| Нет калибровки камеры | Только 2D пиксельные координаты | При интеграции с роботами |
| Нет масштабирования | Один пользователь = один поток | При многопользовательском применении |
| Нет Docker | Ручной запуск трёх сервисов | При развёртывании на production |

---

## 9. Что проверено фактически

| Проверка | Статус |
|---|---|
| Код прочитан и проанализирован полностью | ✅ |
| TypeScript типы проверены через чтение кода | ✅ |
| Python импорты и типы проверены через чтение кода | ✅ |
| Фактический запуск сервисов | ✅ (5 ноября 2026) |
| Работа камеры и детекции end-to-end | ✅ (подтверждено пользователем) |
| Автоматические тесты | ❌ Тестов нет |
| Нагрузочное тестирование | ❌ Не проводилось |
| Проверка утечек памяти (canvas) | ❌ Не проводилась |

---

*Документ создан на основе полного анализа исходного кода проекта.*  
*Этап 1 выполнен 7 ноября 2026. Этап 2 выполнен 7 ноября 2026. Этап 3 выполнен 7 ноября 2026. Следующий шаг: Этап 4 — Detection Pipeline.*
