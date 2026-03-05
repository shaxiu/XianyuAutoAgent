from typing import Any, Callable, Dict, Iterable, Optional

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)

from core.models import Action


class ActionExecutor:
    def __init__(
        self,
        send_msg_func: Optional[Callable[..., Any]],
        set_manual_mode_func: Optional[Callable[[str, bool], None]],
    ):
        self.send_msg_func = send_msg_func
        self.set_manual_mode_func = set_manual_mode_func

    async def execute(self, actions: Iterable[Action], context: Optional[Dict[str, Any]] = None) -> None:
        runtime = context or {}
        for action in actions:
            await self._execute_one(action, runtime)

    async def _execute_one(self, action: Action, runtime: Dict[str, Any]) -> None:
        if action.action_type == "send_text":
            await self._handle_send_text(action.payload, runtime)
            return
        if action.action_type == "set_manual_mode":
            self._handle_set_manual_mode(action.payload)
            return
        logger.warning(f"unknown action_type={action.action_type}, ignored")

    async def _handle_send_text(self, payload: Dict[str, Any], runtime: Dict[str, Any]) -> None:
        if self.send_msg_func is None:
            logger.warning("send_msg_func is not configured, skip send_text")
            return

        websocket = runtime.get("websocket")
        chat_id = payload.get("chat_id")
        to_user_id = payload.get("to_user_id")
        text = payload.get("text")
        if websocket is None:
            logger.warning("websocket is missing in runtime context, skip send_text")
            return
        if not all(isinstance(v, str) and v for v in [chat_id, to_user_id, text]):
            logger.warning(f"invalid send_text payload={payload}")
            return
        await self.send_msg_func(websocket, chat_id, to_user_id, text)

    def _handle_set_manual_mode(self, payload: Dict[str, Any]) -> None:
        if self.set_manual_mode_func is None:
            logger.warning("set_manual_mode_func is not configured, skip set_manual_mode")
            return
        chat_id = payload.get("chat_id")
        enabled = payload.get("enabled")
        if not isinstance(chat_id, str) or not chat_id:
            logger.warning(f"invalid set_manual_mode payload={payload}")
            return
        self.set_manual_mode_func(chat_id, bool(enabled))

