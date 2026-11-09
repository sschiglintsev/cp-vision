"""
CV Service — точка входа FastAPI приложения.

Порядок инициализации при старте (lifespan):
1. Создаётся YoloEngine (без загрузки модели).
2. Вызывается engine.initialize() — модель загружается из файла.
3. Engine регистрируется в ModelRegistry.
4. DetectionService получает доступ к движку через registry.
5. /health/ready начинает возвращать 200.

При остановке приложения вызывается engine.shutdown().

Загрузка модели НЕ происходит при импорте Python-модулей.
YoloEngine импортируется только внутри lifespan (lazy import).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.detect import router as detect_router
from app.api.health import router as health_router
from app.inference.registry import model_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # YoloEngine импортируется здесь — не при загрузке модуля main.py.
    # Это предотвращает загрузку модели (и зависимостей ultralytics) при импорте.
    from app.inference.yolo_engine import YoloEngine

    engine = YoloEngine()
    try:
        engine.initialize()
        model_registry.register(engine)
        logger.info(
            "CV Service ready | engine: %s",
            engine.get_model_info(),
        )
    except Exception as exc:
        # Сервис стартует, но /health/ready вернёт 503.
        logger.error("Failed to initialize inference engine: %s", exc)

    yield

    # Корректное завершение работы движка.
    if model_registry.is_ready():
        try:
            model_registry.get_active_engine().shutdown()
        except RuntimeError:
            pass
    logger.info("CV Service shut down")


app = FastAPI(title="CV Service", version="0.3.0", lifespan=lifespan)

app.include_router(detect_router)
app.include_router(health_router)
