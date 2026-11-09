# Computer Vision Platform

## Быстрый старт

```bash
# Терминал 1 — CV Service (порт 8000)
cd cv-service && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Если порт занят:
lsof -ti :8000 | xargs kill

# Терминал 2 — Backend (порт 3000)
cd backend && npm run dev

# Терминал 3 — Frontend (порт 5173)
cd frontend && npm run dev

# Для доступа с телефона в локальной сети:
# cd frontend && npm run dev -- --host
```

---

## О проекте

Платформа для изучения и разработки систем компьютерного зрения на базе YOLO.

**Что умеет:**
- Принимать видеопоток с браузерной камеры (ноутбук / смартфон)
- Передавать кадры на бэкенд через Socket.IO в реальном времени
- Обрабатывать каждый кадр нейросетью YOLOv11n
- Возвращать координаты обнаруженных объектов обратно на фронтенд
- Рисовать bounding boxes поверх видео без задержки

**Что не поддерживается (намеренно):**
- Загрузка статичных изображений (удалена)
- RTSP, USB, IP-камеры
- Docker / Kubernetes
- Множественные модели

---

## Стек технологий

### Frontend
- React 18 + TypeScript
- Vite 6
- Ant Design 5
- React Router 7
- Socket.IO Client 4
- Axios + JWT (silent refresh)

### Backend
- Node.js + Express + TypeScript
- Socket.IO 4
- PostgreSQL + Prisma ORM
- JWT (access 15 мин / refresh 30 дней в HttpOnly cookie)

### CV Service
- Python 3.9+
- FastAPI + uvicorn
- Ultralytics YOLOv11n
- OpenCV, NumPy, Pillow

---

## Архитектура

```
Browser (getUserMedia)
  │  base64 JPEG, 200 мс интервал
  ↓ Socket.IO  camera:frame
Backend :3000
  │  multipart/form-data HTTP POST
  ↓ axios  POST /detect
CV Service :8000  (YOLOv11n)
  │  { objects: [...] }
  ↓ HTTP response
Backend
  │  { objects, error, timestamp }
  ↓ Socket.IO  detection:frame
Browser (Canvas overlay)
```

Frontend не обращается к CV Service напрямую — только через Backend.

---

## Socket.IO события

| Событие | Направление | Описание |
|---|---|---|
| `camera:frame` | Frontend → Backend | base64 JPEG кадр |
| `detection:frame` | Backend → Frontend | результат детекции |

### Формат `camera:frame` (Frontend → Backend)

```json
{ "frame": "data:image/jpeg;base64,...", "cameraId": "abc123-device-id" }
```

Для обратной совместимости Backend также принимает строку (только `frame` без `cameraId`).

### Формат `detection:frame` (Backend → Frontend)

```json
{
  "objects": [
    { "class": "person", "confidence": 0.97, "x": 100, "y": 120, "width": 150, "height": 200 }
  ],
  "error": null,
  "timestamp": 1731000000000,
  "cameraId": "abc123-device-id",
  "source": { "type": "browser", "id": "abc123-device-id", "name": null },
  "image":  { "width": 1280, "height": 720, "format": "jpeg" },
  "model":  { "id": "yolo11n", "name": "yolo11n", "type": "object-detection" }
}
```

При ошибке детекции `error` содержит строку, `objects` пустой. При успехе `error` — `null`.  
Поля `cameraId`, `source`, `image`, `model` добавлены в Stage 3 и являются опциональными для старых клиентов.

---

## Переменные окружения

### backend/.env

```env
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/cp_vision?schema=public
JWT_SECRET=change-me-access-secret
JWT_REFRESH_SECRET=change-me-refresh-secret
CV_SERVICE_URL=http://localhost:8000
CORS_ORIGIN=http://localhost:5173
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

## Структура репозитория

```
cp-vision/
├── frontend/
│   └── src/
│       ├── api/            — authApi, axios client
│       ├── components/     — AuthInitializer, CameraOverlay, PrivateRoute
│       ├── features/auth/  — useAuth hook
│       ├── hooks/          — useCamera, useCameraDetection, useSocket
│       ├── pages/          — LoginPage, DashboardPage, CameraPage
│       ├── store/          — authStore (in-memory token)
│       └── types/          — auth.ts, detection.ts
│
├── backend/
│   ├── prisma/
│   │   └── schema.prisma
│   └── src/
│       ├── config/         — env.ts, database.ts
│       ├── controllers/    — AuthController
│       ├── middleware/     — auth, errorHandler, validate
│       ├── repositories/   — User, Detection, DetectionResult
│       ├── routes/         — authRoutes
│       ├── services/       — AuthService, CvServiceClient
│       ├── websocket/      — socketEvents.ts
│       └── utils/          — AppError, apiResponse, jwt, logger
│
├── cv-service/
│   └── app/
│       ├── api/
│       │   ├── detect.py   — POST /detect (API-контракт без изменений)
│       │   └── health.py   — /health/live, /health/ready, /health
│       ├── core/
│       │   └── config.py   — Settings (pydantic-settings)
│       ├── inference/
│       │   ├── base.py     — BaseInferenceEngine (ABC)
│       │   ├── yolo_engine.py — YoloEngine(BaseInferenceEngine)
│       │   └── registry.py — ModelRegistry + singleton
│       ├── models/         — detection.py (Pydantic схемы DetectedObject, DetectionResponse)
│       ├── services/       — detection_service.py (DetectionService → BaseInferenceEngine)
│       └── main.py         — FastAPI app, lifespan (инициализация engine)
│
├── docs/
│   └── ARCHITECTURE_AUDIT.md
├── PROGRESS.md
└── README.md
```

---

## Inference Engine (CV Service)

CV Service построен на абстракции `BaseInferenceEngine`:

| Компонент | Ответственность |
|---|---|
| `BaseInferenceEngine` | ABC-интерфейс: `initialize`, `detect`, `get_model_info`, `is_ready`, `shutdown` |
| `YoloEngine` | Реализация для YOLOv11n: загрузка .pt, инференс, конвертация в `DetectedObject` |
| `ModelRegistry` | Хранит активный движок, предоставляет `get_active_engine()`, `is_ready()` |
| `DetectionService` | Вызывает движок через `BaseInferenceEngine`, не зависит от YOLO |

Модель загружается **один раз** в `lifespan` через `engine.initialize()`. При импорте Python-модулей загрузки не происходит.

---

## Health endpoints (CV Service)

| Endpoint | Описание |
|---|---|
| `GET /health` | Liveness — приложение запущено (backward compat) |
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe — 503 если движок не готов |

---

## Аутентификация

- Регистрация и вход по email + пароль
- Access token (15 мин) хранится в памяти — не в localStorage
- Refresh token (30 дней) в HttpOnly cookie
- Silent refresh при перезагрузке страницы через `AuthInitializer`
- Axios interceptor обновляет access token при 401, не перехватывает `/auth/refresh`

---

## Roadmap

| Приоритет | Задача |
|---|---|
| ⬆ | История детекций — сохранение в БД, список сессий |
| ⬆ | Фильтрация классов (показывать только person / car и т.д.) |
| ⬆ | Смена модели через UI (yolo11n / yolo11s / yolo11m) |
| → | Обработка видеофайла (загрузка mp4, покадровая обработка) |
| → | Статистика за сессию |
| ↓ | RTSP-камеры |
| ↓ | Face recognition |
| ↓ | Docker / Kubernetes |
