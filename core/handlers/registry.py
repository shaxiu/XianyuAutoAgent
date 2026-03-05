import importlib
import os
from typing import List, Optional

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)

from core.handlers.base import EventHandler


def load_handlers_from_env(handler_paths: Optional[str] = None) -> List[EventHandler]:
    if handler_paths is None:
        handler_paths = os.getenv("EVENT_HANDLERS", "")

    handlers: List[EventHandler] = []
    for path in _split_paths(handler_paths):
        handler = _load_handler(path)
        if handler is not None:
            handlers.append(handler)
    return handlers


def _split_paths(handler_paths: str) -> List[str]:
    if not isinstance(handler_paths, str):
        return []
    return [part.strip() for part in handler_paths.split(",") if part.strip()]


def _load_handler(path: str) -> Optional[EventHandler]:
    try:
        module_name, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        klass = getattr(module, class_name)
        instance = klass()
        if not isinstance(instance, EventHandler):
            logger.warning(f"handler {path} is not EventHandler, skipped")
            return None
        return instance
    except Exception as exc:
        logger.warning(f"failed to load handler {path}: {exc}")
        return None
