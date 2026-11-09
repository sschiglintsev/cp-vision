from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.inference.registry import model_registry

router = APIRouter()


@router.get("/health/live")
async def liveness() -> Dict[str, str]:
    """Liveness probe: приложение запущено."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> Any:
    """Readiness probe: движок инициализирован и готов к инференсу.

    Возвращает HTTP 503 если модель ещё не загружена или загрузка завершилась ошибкой.
    """
    if not model_registry.is_ready():
        info = model_registry.get_model_info()
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "model": info.get("name", "unknown"),
            },
        )
    info = model_registry.get_model_info()
    return {"status": "ready", "model": info.get("name", "unknown")}


@router.get("/health")
async def health() -> Dict[str, str]:
    """Liveness (обратная совместимость со Stage 1)."""
    return {"status": "ok"}
