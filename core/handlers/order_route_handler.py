import hashlib
import hmac
import json
import os
from typing import Any, Callable, Dict, List, Optional

import requests

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)

from core.handlers.base import EventHandler
from core.handlers.webhook_handler import _parse_actions, _to_bool, _to_int
from core.models import Action, Event


class OrderRouteHandler(EventHandler):
    name = "order_route"

    def __init__(
        self,
        routes: Optional[Dict[str, Dict[str, Any]]] = None,
        group_routes: Optional[Dict[str, Dict[str, Any]]] = None,
        item_id_resolver: Optional[Callable[[str], Optional[str]]] = None,
        enabled: Optional[bool] = None,
        default_timeout_ms: Optional[int] = None,
        default_retries: Optional[int] = None,
    ):
        item_routes = _normalize_item_routes(routes if routes is not None else _load_item_routes_from_env())
        grouped_item_routes = _normalize_group_routes(
            group_routes if group_routes is not None else _load_group_routes_from_env()
        )
        self.routes = dict(grouped_item_routes)
        self.routes.update(item_routes)
        self.item_id_resolver = item_id_resolver or (lambda chat_id: None)
        self.enabled = (
            _to_bool(os.getenv("ORDER_ROUTER_ENABLED", "true")) if enabled is None else bool(enabled)
        )
        self.default_timeout_ms = (
            _to_int(os.getenv("ORDER_ROUTER_TIMEOUT_MS", "3000"), 3000)
            if default_timeout_ms is None
            else int(default_timeout_ms)
        )
        self.default_retries = (
            _to_int(os.getenv("ORDER_ROUTER_RETRIES", "2"), 2)
            if default_retries is None
            else int(default_retries)
        )

    def handle(self, event: Event) -> List[Action]:
        if not self.enabled or event.event_type != "order.status.changed":
            return []

        payload = event.payload if isinstance(event.payload, dict) else {}
        chat_id = payload.get("chat_id")
        item_id = payload.get("item_id")
        if not item_id and isinstance(chat_id, str) and chat_id:
            item_id = self.item_id_resolver(chat_id)

        if not isinstance(item_id, str) or not item_id:
            logger.debug(f"order event without item_id skipped event_id={event.event_id}")
            return []

        route = self.routes.get(item_id)
        if not route:
            logger.debug(f"order event item_id={item_id} has no route, skip")
            return []

        url = route.get("url")
        if not isinstance(url, str) or not url.strip():
            logger.warning(f"order route item_id={item_id} has invalid url")
            return []

        normalized_payload = dict(payload)
        normalized_payload["item_id"] = item_id
        body = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "payload": normalized_payload,
            "meta": event.meta,
        }

        headers = {"Content-Type": "application/json"}
        secret = route.get("secret", "")
        if isinstance(secret, str) and secret:
            body_json = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = hmac.new(secret.encode("utf-8"), body_json.encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-Agent-Signature"] = f"sha256={digest}"

        retries = _to_int(str(route.get("retries", self.default_retries)), self.default_retries)
        timeout_ms = _to_int(str(route.get("timeout_ms", self.default_timeout_ms)), self.default_timeout_ms)

        attempts = max(retries, 0) + 1
        timeout = max(timeout_ms, 1) / 1000.0
        for attempt in range(attempts):
            try:
                response = requests.post(url.strip(), json=body, headers=headers, timeout=timeout)
            except Exception as exc:
                logger.warning(
                    f"order route call failed item_id={item_id} attempt={attempt + 1}/{attempts} err={exc}"
                )
                continue

            if 200 <= response.status_code < 300:
                return _parse_actions(response)

            logger.warning(
                f"order route non-2xx item_id={item_id} attempt={attempt + 1}/{attempts} status={response.status_code}"
            )

        return []


def _load_item_routes_from_env() -> Dict[str, Dict[str, Any]]:
    raw = os.getenv("ORDER_ITEM_WEBHOOK_ROUTES", "{}").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.warning(f"invalid ORDER_ITEM_WEBHOOK_ROUTES config: {exc}")
    return {}


def _load_group_routes_from_env() -> Dict[str, Dict[str, Any]]:
    raw = os.getenv("ORDER_GROUP_WEBHOOK_ROUTES", "{}").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.warning(f"invalid ORDER_GROUP_WEBHOOK_ROUTES config: {exc}")
    return {}


def _normalize_item_routes(routes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for item_id, config in routes.items():
        if not isinstance(item_id, str) or not item_id:
            continue

        if isinstance(config, str):
            normalized[item_id] = {"url": config.strip()}
            continue

        if not isinstance(config, dict):
            continue

        route = dict(config)
        if "url" not in route and isinstance(route.get("webhook_url"), str):
            route["url"] = route["webhook_url"]
        normalized[item_id] = route
    return normalized


def _normalize_group_routes(group_routes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for group_name, config in group_routes.items():
        if not isinstance(config, dict):
            continue
        items = config.get("items")
        if not isinstance(items, list):
            logger.warning(f"order group={group_name} missing items list, skipped")
            continue

        route = dict(config)
        route.pop("items", None)
        if "url" not in route and isinstance(route.get("webhook_url"), str):
            route["url"] = route["webhook_url"]

        for item_id in items:
            if not isinstance(item_id, str) or not item_id:
                continue
            normalized[item_id] = route
    return normalized
