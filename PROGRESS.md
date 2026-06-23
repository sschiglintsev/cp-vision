# CP Vision — Progress Log

Документ описывает всё, что реализовано в проекте с нуля по состоянию на 23 июня 2026.

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
        │   └── detect.py           — POST /detect
        ├── models/
        │   └── detection.py        — Pydantic схемы
        ├── services/
        │   └── detection_service.py — YoloDetectionService (модель один раз)
        └── utils/
            └── config.py           — Settings (pydantic-settings)
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
- Модель загружается один раз при старте
- Порог уверенности: 0.4 (настраивается через `YOLO_CONFIDENCE` в `.env`)
- 80 классов: person, car, cat, dog, bottle, laptop, phone и др.

### WebSocket (Socket.IO)
- Аутентификация через токен в handshake
- Персональные комнаты `user:<id>` для изоляции событий

---

## Переменные окружения

### backend/.env
```env
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/cp_vision?schema=public
JWT_SECRET=...
JWT_REFRESH_SECRET=...
CV_SERVICE_URL=http://localhost:8000
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
- CV Service при первом запуске скачивает модель (~5 МБ) из интернета
- При перезапуске CV Service с `--reload` модель перезагружается (~2–3 сек)
- Порт 3000 может быть занят другими приложениями (Next.js и др.) — проверять через `lsof -i :3000`
- `DetectionRepository` и `DetectionResultRepository` существуют в коде, но не вызываются — задел на будущее
