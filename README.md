# Computer Vision Platform

запуск
# Терминал 1
cd cv-service && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
(если что убить процесс lsof -ti :8000 | xargs kill)

# Терминал 2
cd backend && npm run dev

# Терминал 3
cd frontend && npm run dev

## Project Overview

Проект предназначен для изучения и разработки систем компьютерного зрения на базе YOLO.

Основная цель проекта:

* прием изображений и видеопотока от пользователя;
* передача данных на CV-сервис;
* обработка кадров нейросетью;
* получение координат обнаруженных объектов;
* отображение результатов в реальном времени на фронтенде;
* дальнейшее развитие проекта в сторону трекинга объектов, распознавания лиц, аналитики и видеообработки.

---

# Technology Stack

## Frontend

* React
* TypeScript
* Vite
* Ant Design
* React Router
* Socket.IO Client
* Axios
* JWT Authentication

## Backend

* Node.js
* Express
* TypeScript
* PostgreSQL
* Socket.IO
* JWT Authentication
* Prisma ORM (предпочтительно)
* Docker

## CV Service

* Python 3.12+
* FastAPI
* OpenCV
* Ultralytics YOLO
* NumPy
* PyTorch

---

# Repository Structure

```text
root/

├── frontend/
│   ├── src/
│   ├── public/
│   ├── .env
│   └── package.json
│
├── backend/
│   ├── src/
│   ├── migrations/
│   ├── prisma/
│   ├── .env
│   └── package.json
│
├── cv-service/
│   ├── app/
│   ├── models/
│   ├── uploads/
│   ├── .env
│   └── requirements.txt
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# System Architecture

```text
Frontend
    |
    | WebSocket / HTTP
    |
Backend
    |
    | HTTP API
    |
CV Service (Python + YOLO)
```

### Processing Flow

1. Пользователь загружает изображение или видео.
2. Frontend отправляет файл на Backend.
3. Backend сохраняет задачу.
4. Backend отправляет запрос в CV Service.
5. CV Service запускает YOLO.
6. YOLO возвращает список найденных объектов.
7. Backend передает результат через WebSocket.
8. Frontend отображает bounding boxes поверх изображения или видео.

---

# Data Exchange Format

## Detection Result

```json
{
  "frameId": 1,
  "objects": [
    {
      "class": "person",
      "confidence": 0.97,
      "x": 100,
      "y": 120,
      "width": 150,
      "height": 200
    }
  ]
}
```

---

# Real-Time Communication

Для передачи результатов использовать Socket.IO.

Frontend подписывается на события:

```text
detection:start
detection:frame
detection:finish
detection:error
```

Backend является Socket.IO сервером.

CV Service не работает напрямую с WebSocket клиентами.

Все взаимодействие CV Service → Frontend должно проходить через Backend.

---

# Authentication

Использовать JWT.

## Access Token

* срок жизни 15 минут

## Refresh Token

* срок жизни 30 дней

Хранение:

* Access Token в памяти приложения
* Refresh Token в HttpOnly Cookie

Не использовать localStorage для access token.

---

# Database

PostgreSQL.

Основные сущности:

## Users

```text
id
email
password_hash
created_at
```

## Detections

```text
id
user_id
file_name
status
created_at
```

## DetectionResults

```text
id
detection_id
class_name
confidence
x
y
width
height
```

---

# Backend Guidelines

## Architecture

Использовать слои:

```text
Controller
Service
Repository
Database
```

Не обращаться к БД напрямую из контроллеров.

---

# Frontend Guidelines

Использовать структуру:

```text
src/

api/
components/
features/
pages/
hooks/
store/
types/
utils/
```

Каждая feature должна быть максимально независимой.

Не размещать бизнес-логику внутри UI-компонентов.

---

# CV Service Guidelines

Использовать архитектуру:

```text
app/

api/
services/
models/
utils/
```

YOLO модели загружаются один раз при старте приложения.

Не загружать модель на каждый запрос.

---

# Environment Variables

Каждый сервис обязан иметь собственный .env.

Пример:

## frontend

```env
VITE_API_URL=
VITE_WS_URL=
```

## backend

```env
PORT=
DATABASE_URL=
JWT_SECRET=
JWT_REFRESH_SECRET=
CV_SERVICE_URL=
```

## cv-service

```env
YOLO_MODEL=
HOST=
PORT=
```

---

# Code Style

## TypeScript

* strict mode
* eslint
* prettier

## Python

* black
* isort
* flake8

---

# Future Roadmap

## Stage 1

* JWT авторизация
* загрузка изображений
* YOLO detection
* отображение bounding boxes

## Stage 2

* обработка видео
* WebSocket streaming
* трекинг объектов

## Stage 3

* face detection
* face recognition
* аналитика

## Stage 4

* RTSP камеры
* многопоточность
* GPU ускорение

## Stage 5

* кластеризация сервисов
* Kubernetes
* масштабирование

```
```
