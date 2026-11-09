# CP Vision — Progress Log

Документ описывает всё, что реализовано в проекте с нуля.  
Последнее обновление: **7 ноября 2026** (Stage 3 — Universal Detection Result).

---

## Текущее состояние

Проект полностью рабочий. Реализован стриминг с камеры (ноутбук / телефон) с детекцией объектов в реальном времени через YOLOv11.

**Функционал загрузки статичных изображений удалён** — только живая камера.

---

## Архитектура

```
Browser / Phone (Camera)
  ↕ Socket.IO  (camera:frame → detection:frame)
Backend  :3000  (Node.js + Express + Socket.IO)
  ↕ HTTP POST /detect
CV Service  :8000  (Python + FastAPI + YOLOv11)
  ↕ PostgreSQL  :5432
```

- Frontend не обращается к CV Service напрямую — только через Backend.
- Все результаты детекции возвращаются через WebSocket.

---

## Команды запуска

### CV Service (порт 8000)
```bash
cd cv-service
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Backend (порт 3000)
```bash
cd backend
yarn dev
```

### Frontend (порт 5173)
```bash
cd frontend
yarn dev

# для доступа с телефона в локальной сети:
yarn dev --host
```

### База данных
```bash
cd backend
npx prisma migrate deploy
```

---

## Структура проекта

```
cp-vision/
├── frontend/
│   └── src/
│       ├── api/
│       │   ├── authApi.ts          — register, login, refresh, logout
│       │   └── client.ts           — axios instance, interceptor refresh
│       ├── components/
│       │   ├── AuthInitializer/    — восстановление сессии при перезагрузке
│       │   ├── CameraOverlay/      — canvas bounding boxes поверх видео
│       │   └── PrivateRoute/       — защита маршрутов
│       ├── features/auth/
│       │   └── useAuth.ts          — login / register / logout хук
│       ├── hooks/
│       │   ├── useCamera.ts        — getUserMedia, захват кадра
│       │   ├── useCameraDetection.ts — отправка кадров, sticky TTL
│       │   └── useSocket.ts        — Socket.IO подключение
│       ├── pages/
│       │   ├── LoginPage.tsx       — вход + регистрация (вкладки)
│       │   ├── DashboardPage.tsx   — приветствие, кнопка на камеру
│       │   └── CameraPage.tsx      — главная страница с камерой
│       ├── store/
│       │   └── authStore.ts        — in-memory: access token + user
│       └── types/
│           ├── auth.ts
│           └── detection.ts
│
├── backend/
│   ├── prisma/
│   │   └── schema.prisma           — User, Detection, DetectionResult
│   └── src/
│       ├── config/
│       │   ├── database.ts         — Prisma client
│       │   └── env.ts              — переменные окружения
│       ├── controllers/
│       │   └── AuthController.ts   — register, login, refresh, logout
│       ├── middleware/
│       │   ├── auth.ts             — JWT Bearer middleware
│       │   ├── errorHandler.ts     — централизованная обработка ошибок
│       │   └── validate.ts         — Zod-валидация
│       ├── repositories/
│       │   ├── UserRepository.ts
│       │   ├── DetectionRepository.ts      — для будущей истории
│       │   └── DetectionResultRepository.ts
│       ├── routes/
│       │   └── authRoutes.ts
│       ├── services/
│       │   ├── AuthService.ts      — bcrypt, JWT, refresh
│       │   └── CvServiceClient.ts  — HTTP к CV Service
│       ├── types/
│       │   ├── auth.ts
│       │   └── detection.ts
│       ├── utils/
│       │   ├── AppError.ts
│       │   ├── apiResponse.ts      — sendSuccess / sendError
│       │   ├── jwt.ts              — sign/verify access+refresh
│       │   └── logger.ts
│       ├── websocket/
│       │   └── socketEvents.ts     — camera:frame → detectBuffer → detection:frame
│       ├── app.ts
│       └── index.ts
│
└── cv-service/
    └── app/
        ├── api/
        │   ├── detect.py           — POST /detect
        │   └── health.py           — /health/live, /health/ready, /health
        ├── core/
        │   └── config.py           — Settings (pydantic-settings)
        ├── inference/
        │   ├── base.py             — BaseInferenceEngine (ABC)
        │   ├── yolo_engine.py      — YoloEngine(BaseInferenceEngine)
        │   └── registry.py         — ModelRegistry + singleton
        ├── models/
        │   └── detection.py        — Pydantic схемы
        ├── services/
        │   └── detection_service.py — DetectionService → BaseInferenceEngine
        └── main.py                 — lifespan с инициализацией engine
```

---

## Реализованный функционал

### Аутентификация
- Регистрация и вход через email + пароль
- JWT: access token (15 мин) в памяти, refresh token (30 дней) в HttpOnly cookie
- Автоматическое обновление access token при истечении (axios interceptor)
- **Silent refresh при перезагрузке страницы** — сессия восстанавливается автоматически
- Защищённые маршруты через `PrivateRoute`

### Стриминг с камеры
- Доступ к камере через `getUserMedia`
- Выбор камеры (если несколько — фронтальная / задняя / внешняя)
- Кадры захватываются каждые 200 мс, отправляются через Socket.IO (`camera:frame`)
- Backend получает кадр → вызывает CV Service → возвращает результат (`detection:frame`)
- Bounding boxes рисуются на `<canvas>` поверх `<video>` в реальном времени
- **Sticky TTL 600 мс** — bounding boxes не мигают при пропуске кадра
- Backpressure — следующий кадр не отправляется, пока не обработан предыдущий

### CV Service
- YOLOv11n (точнее и быстрее YOLOv8n)
- Модель загружается один раз в lifespan через `YoloEngine.initialize()` — не при импорте модуля
- Порог уверенности: 0.4 (настраивается через `YOLO_CONFIDENCE` в `.env`)
- 80 классов: person, car, cat, dog, bottle, laptop, phone и др.
- **Inference Engine абстракция** (Stage 2): `BaseInferenceEngine` ABC + `YoloEngine` + `ModelRegistry` + `DetectionService`
- **Universal Detection Result** (Stage 3): `DetectionResult` с `cameraId`, `source`, `image`, `model`; `camera:frame` передаёт `{frame, cameraId}`; `detection:frame` обогащён метаданными

### WebSocket (Socket.IO)
- Аутентификация через токен в handshake
- Персональные комнаты `user:<id>` для изоляции событий
- Формат `detection:frame`: `{ objects, error, timestamp }` — ошибка отделена от пустого результата

---

## Переменные окружения

### backend/.env
```env
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/cp_vision?schema=public
JWT_SECRET=...
JWT_REFRESH_SECRET=...
CV_SERVICE_URL=http://localhost:8000
CORS_ORIGIN=http://localhost:5173
NODE_ENV=development
```

### frontend/.env
```env
VITE_API_URL=http://localhost:3000
VITE_WS_URL=http://localhost:3000
```

### cv-service/.env
```env
HOST=0.0.0.0
PORT=8000
YOLO_MODEL=yolo11n.pt
YOLO_CONFIDENCE=0.4
```

---

## Зависимости

### Frontend
| Пакет | Назначение |
|---|---|
| React 18 + TypeScript | UI |
| Vite 6 | сборщик |
| Ant Design 5 | UI-компоненты |
| React Router 7 | роутинг |
| Axios | HTTP-клиент |
| Socket.IO Client 4 | WebSocket |

### Backend
| Пакет | Назначение |
|---|---|
| Express 4 | HTTP-сервер |
| Prisma 6 + @prisma/client | ORM |
| Socket.IO 4 | WebSocket-сервер |
| jsonwebtoken | JWT |
| bcryptjs | хэширование паролей |
| cookie-parser | чтение HttpOnly cookie |
| axios | HTTP к CV Service |
| zod | валидация запросов |
| tsx | запуск TypeScript |

### CV Service
| Пакет | Назначение |
|---|---|
| FastAPI | HTTP-фреймворк |
| uvicorn | ASGI-сервер |
| ultralytics | YOLOv11 |
| opencv-python-headless | обработка изображений |
| numpy | работа с массивами |
| Pillow | декодирование изображений |
| pydantic-settings | конфигурация |

---

## База данных (PostgreSQL)

### Таблицы
- `users` — id, email, password_hash, created_at, updated_at
- `detections` — id, user_id, file_name, status (PENDING/PROCESSING/COMPLETED/FAILED), created_at, updated_at
- `detection_results` — id, detection_id, class_name, confidence, x, y, width, height, created_at, updated_at

> `detections` и `detection_results` в коде не используются (репозитории готовы) — зарезервированы для будущей истории.

---

## Что можно сделать следующим

| Приоритет | Задача |
|---|---|
| ⬆ | История детекций — список сессий, сохранение в БД |
| ⬆ | Смена модели через UI (yolo11n / yolo11s / yolo11m) |
| ⬆ | Фильтрация классов — показывать только person / car / etc |
| → | Обработка видеофайла (загрузка mp4, покадровая обработка) |
| → | Статистика — сколько объектов каждого класса найдено за сессию |
| → | Профиль пользователя — смена пароля |
| ↓ | Face recognition (отдельная модель) |
| ↓ | RTSP-камеры |
| ↓ | Docker / Kubernetes |

---

## Известные особенности

- Access token хранится в памяти — при открытии новой вкладки происходит silent refresh автоматически
- **Refresh token живёт 30 дней** — после истечения нужно войти заново (спиннер не крутится, форма показывается)
- CV Service при первом запуске скачивает модель (~5 МБ) из интернета
- При перезапуске CV Service с `--reload` модель перезагружается (~2–3 сек)
- Порт 3000 может быть занят другими приложениями (Next.js и др.) — проверять через `lsof -i :3000`
- `DetectionRepository` и `DetectionResultRepository` существуют в коде, но не вызываются — задел на будущее

## Исправления

### 7 ноября 2026 — Stage 3: Universal Detection Result

**CV Service:**
- **`app/models/detection.py`** — добавлены `CameraSourceType` (enum), `SourceMetadata`, `ImageMetadata`, `ModelMetadata`, `DetectionResult`; `DetectedObject` и `DetectionResponse` сохранены
- **`app/inference/yolo_engine.py`** — `get_model_info()` теперь включает ключ `"id"` (напр. `"yolo11n"`)
- **`app/services/detection_service.py`** — `detect()` принимает `camera_id`, `source_type`, `source_name`; читает размеры изображения через Pillow; строит полный `DetectionResult`
- **`app/api/detect.py`** — добавлены опциональные Form-поля `camera_id`, `source_type`, `source_name`; backward compat сохранена (запросы без метаданных работают)

**Backend:**
- **`src/types/detection.ts`** — добавлены `CameraSourceType`, `SourceMetadataDto`, `ImageMetadataDto`, `ModelMetadataDto`, `CvDetectionResult`
- **`src/services/CvServiceClient.ts`** — `detectBuffer` принимает `DetectBufferOptions`; передаёт `camera_id`, `source_type` в CV Service; возвращает `CvDetectionResult`
- **`src/websocket/socketEvents.ts`** — `camera:frame` принимает `string | {frame, cameraId}` (backward compat); `detection:frame` обогащён полями `cameraId`, `source`, `image`, `model`

**Frontend:**
- **`src/types/detection.ts`** — добавлены `CameraSourceType`, `SourceMetadata`, `ImageMetadata`, `ModelMetadata`, `DetectionResult`
- **`src/hooks/useCameraDetection.ts`** — принимает `cameraId?: string | null`; `camera:frame` эмитируется как `{frame, cameraId}`; `DetectionFramePayload` расширен опциональными полями
- **`src/pages/CameraPage.tsx`** — передаёт `activeDeviceId` как `cameraId`

---

### 7 ноября 2026 — Stage 2: Inference Engine Abstraction

**CV Service:**
- **`app/core/config.py`** — создан `core/` пакет, `Settings` перенесена из `utils/config.py`
- **`app/inference/base.py`** — `BaseInferenceEngine` ABC: `initialize`, `detect`, `get_model_info`, `is_ready`, `shutdown`; независим от YOLO и любых ML-библиотек
- **`app/inference/yolo_engine.py`** — `YoloEngine(BaseInferenceEngine)`: инкапсулирует всю YOLO-специфику; модель загружается в `initialize()`, не в `__init__`
- **`app/inference/registry.py`** — `ModelRegistry` + singleton `model_registry`; хранит активный движок, предоставляет `get_active_engine()`, `is_ready()`
- **`app/services/detection_service.py`** — `DetectionService` работает через `BaseInferenceEngine`; не зависит от YOLO напрямую; singleton `detection_service = DetectionService(registry=model_registry)`
- **`app/api/health.py`** — health/live, health/ready, health вынесены в отдельный роутер; readiness проверяет `model_registry.is_ready()`
- **`app/api/detect.py`** — API-контракт без изменений (POST /detect, тот же формат ответа)
- **`app/main.py`** — lifespan без import-time загрузки модели; `YoloEngine` импортируется только внутри lifespan; при ошибке инициализации сервис стартует, но `/health/ready` возвращает 503
- **`app/utils/config.py`** — удалён (контент перенесён в `core/config.py`)

**Устранена проблема Stage 1:** ранее `detection_service = YoloDetectionService()` запускался на уровне модуля при импорте — YOLO загружалась до lifespan, `try/except` не мог поймать ошибку. Теперь загрузка только в lifespan.

---

### 7 ноября 2026 — Stage 1: MVP Stabilization

**Frontend:**
- **`hooks/useSocket.ts`** — исправлен stale ref: socket теперь возвращается через `useState`, компоненты гарантированно получают реальный instance после коннекта
- **`hooks/useCameraDetection.ts`** — ошибка детекции отделена от пустого результата: добавлено поле `detectionError: string | null`; при `data.error` показывается Alert, sticky TTL применяется только при успешном ответе
- **`hooks/useCamera.ts`** — canvas для захвата кадра переиспользуется (`captureCanvasRef`) — один элемент вместо 5 аллокаций/сек
- **`components/CameraOverlay/CameraOverlay.tsx`** — добавлен независимый `resize` listener, bounding boxes корректно перерисовываются при изменении размера окна
- **`pages/CameraPage.tsx`** — показывается `<Alert type="error">` при ошибке детекции

**Backend:**
- **`config/env.ts`** — добавлена переменная `corsOrigin` (читается из `CORS_ORIGIN` или дефолт `http://localhost:5173`)
- **`app.ts`** — CORS origin вынесен из хардкода в `env.corsOrigin`
- **`websocket/socketEvents.ts`** — эмитит `{ objects, error, timestamp }`: при успехе `error: null`, при ошибке — строка с причиной; CORS origin из env; ошибка одного пользователя не влияет на остальных
- **`services/CvServiceClient.ts`** — удалён мёртвый метод `detect(file: Express.Multer.File)`, остался только `detectBuffer`

**CV Service:**
- **`app/utils/config.py`** — дефолт `yolo_model` исправлен с `"yolov8n.pt"` на `"yolo11n.pt"`
- **`app/main.py`** — `@app.on_event("startup")` заменён на `@asynccontextmanager lifespan`; добавлены отдельные endpoints: `GET /health/live` (liveness) и `GET /health/ready` (readiness, 503 если модель не загружена); `GET /health` сохранён для обратной совместимости

**Ранее (7 ноября 2026):**
- **`api/client.ts`** — interceptor теперь не перехватывает 401 от `/auth/refresh`, иначе при истёкшем refresh token возникал бесконечный цикл и спиннер не исчезал
