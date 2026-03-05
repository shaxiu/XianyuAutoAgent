import hashlib
import hmac
import json
import os
from typing import Any, Dict, List

import requests

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)

from core.handlers.base import EventHandler
from core.models import Action, Event


class WebhookHandler(EventHandler):
    name = "webhook"

    def __init__(
        self,
        enabled: bool = None,
        url: str = None,
        timeout_ms: int = None,
        retries: int = None,
        secret: str = None,
    ):
        self.enabled = _to_bool(os.getenv("EVENT_WEBHOOK_ENABLED", "false")) if enabled is None else bool(enabled)
        self.url = (os.getenv("EVENT_WEBHOOK_URL", "") if url is None else url).strip()
        self.timeout_ms = _to_int(os.getenv("EVENT_WEBHOOK_TIMEOUT_MS", "3000"), 3000) if timeout_ms is None else int(timeout_ms)
        self.retries = _to_int(os.getenv("EVENT_WEBHOOK_RETRIES", "2"), 2) if retries is None else int(retries)
        self.secret = os.getenv("EVENT_WEBHOOK_SECRET", "") if secret is None else secret

    def handle(self, event: Event) -> List[Action]:
        if not self.enabled or not self.url:
            return []

        body = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "payload": event.payload,
            "meta": event.meta,
        }
        body_json = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        headers = {
            "Content-Type": "application/json",
        }
        if self.secret:
            signature = hmac.new(self.secret.encode("utf-8"), body_json.encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-Agent-Signature"] = f"sha256={signature}"

        attempts = max(self.retries, 0) + 1
        timeout = max(self.timeout_ms, 1) / 1000.0
        for attempt in range(attempts):
            try:
                response = requests.post(self.url, json=body, headers=headers, timeout=timeout)
            except Exception as exc:
                logger.warning(f"webhook call failed attempt={attempt + 1}/{attempts} err={exc}")
                continue

            if 200 <= response.status_code < 300:
                return _parse_actions(response)

            logger.warning(
                f"webhook non-2xx attempt={attempt + 1}/{attempts} status={response.status_code}"
            )
        return []


def _parse_actions(response: Any) -> List[Action]:
    try:
        data = response.json()
    except Exception:
        return []

    action_items = []
    if isinstance(data, list):
        action_items = data
    elif isinstance(data, dict) and isinstance(data.get("actions"), list):
        action_items = data.get("actions", [])

    actions: List[Action] = []
    for item in action_items:
        if not isinstance(item, dict):
            continue
        action_type = item.get("action_type")
        payload = item.get("payload")
        if not isinstance(action_type, str) or not isinstance(payload, dict):
            continue
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        actions.append(Action(action_type=action_type, payload=payload, meta=meta))
    return actions


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default
