import logging

from fastapi import FastAPI

from app.api.detect import router as detect_router
from app.utils.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CV Service", version="0.1.0")
app.include_router(detect_router)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("CV Service started on %s:%s", settings.host, settings.port)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
