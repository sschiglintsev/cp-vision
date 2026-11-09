"""
ModelRegistry — реестр зарегистрированных Inference Engine.

Хранит активный движок и предоставляет единую точку доступа к нему.
На данном этапе поддерживается один активный движок.

Singleton `model_registry` создаётся на уровне модуля без загрузки модели.
Регистрация движка происходит в lifespan после его инициализации.
"""

import logging
from typing import Dict, Optional

from app.inference.base import BaseInferenceEngine

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Реестр inference engines. Хранит активный движок."""

    def __init__(self) -> None:
        self._engine: Optional[BaseInferenceEngine] = None

    def register(self, engine: BaseInferenceEngine) -> None:
        """Зарегистрировать движок как активный.

        Args:
            engine: Инициализированный экземпляр BaseInferenceEngine.
        """
        self._engine = engine
        logger.info("ModelRegistry: engine registered — %s", engine.get_model_info())

    def get_active_engine(self) -> BaseInferenceEngine:
        """Вернуть активный движок.

        Raises:
            RuntimeError: Если ни один движок не зарегистрирован.
        """
        if self._engine is None:
            raise RuntimeError("No inference engine registered in ModelRegistry")
        return self._engine

    def is_ready(self) -> bool:
        """Вернуть True если активный движок существует и готов."""
        return self._engine is not None and self._engine.is_ready()

    def get_model_info(self) -> Dict[str, str]:
        """Вернуть метаданные активного движка или пустой словарь."""
        if self._engine is None:
            return {}
        return self._engine.get_model_info()


# Singleton — создаётся при импорте модуля без загрузки модели.
# Регистрация движка выполняется в lifespan приложения.
model_registry = ModelRegistry()
