from typing import List

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)

from core.handlers.base import EventHandler
from core.models import Action, Event


class LogHandler(EventHandler):
    name = "log"

    def handle(self, event: Event) -> List[Action]:
        logger.info(f"event={event.event_type} id={event.event_id} payload={event.payload}")
        return []
