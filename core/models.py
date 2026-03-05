from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Event:
    event_id: str
    event_type: str
    occurred_at: int
    payload: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    action_type: str
    payload: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)

