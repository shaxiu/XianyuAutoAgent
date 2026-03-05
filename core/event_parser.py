import hashlib
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from core.models import Event


def parse_events(message_data: Dict[str, Any]) -> List[Event]:
    if not isinstance(message_data, dict):
        return []

    events: List[Event] = []
    order_status = _extract_order_status(message_data)
    if order_status:
        payload = {
            "chat_id": _normalize_id(message_data.get("2")),
            "user_id": _normalize_id(message_data.get("1")),
            "item_id": None,
            "order_status": order_status,
            "raw": message_data,
        }
        events.append(
            Event(
                event_id=_build_event_id("order.status.changed", message_data),
                event_type="order.status.changed",
                occurred_at=int(time.time() * 1000),
                payload=payload,
            )
        )

    if _is_chat_message(message_data):
        message_node = message_data["1"]
        content_node = message_node["10"]
        reminder_url = content_node.get("reminderUrl", "")
        occurred_at = _parse_int(message_node.get("5"), default=int(time.time() * 1000))
        payload = {
            "chat_id": _normalize_id(message_node.get("2")),
            "user_id": _normalize_id(content_node.get("senderUserId")),
            "item_id": _extract_item_id(reminder_url),
            "order_status": _extract_order_status(message_data),
            "message": content_node.get("reminderContent"),
            "sender_name": content_node.get("reminderTitle"),
            "created_at": occurred_at,
            "raw": message_data,
        }
        events.append(
            Event(
                event_id=_build_event_id("chat.message.received", message_data),
                event_type="chat.message.received",
                occurred_at=occurred_at,
                payload=payload,
            )
        )

    return events


def _is_chat_message(message: Dict[str, Any]) -> bool:
    node = message.get("1")
    if not isinstance(node, dict):
        return False
    content = node.get("10")
    return isinstance(content, dict) and "reminderContent" in content


def _extract_order_status(message: Dict[str, Any]) -> Optional[str]:
    node = message.get("3")
    if not isinstance(node, dict):
        return None
    reminder = node.get("redReminder")
    if isinstance(reminder, str) and reminder:
        return reminder
    return None


def _extract_item_id(reminder_url: str) -> Optional[str]:
    if not isinstance(reminder_url, str) or not reminder_url:
        return None
    try:
        parsed = urlparse(reminder_url)
        query = parse_qs(parsed.query)
        item_values = query.get("itemId")
        if item_values:
            return item_values[0]
    except Exception:
        return None
    return None


def _normalize_id(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    if value.endswith("@goofish"):
        return value.split("@", 1)[0]
    return value


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _build_event_id(event_type: str, payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{event_type}:{normalized}".encode("utf-8")).hexdigest()[:24]
    return f"{event_type}:{digest}"

