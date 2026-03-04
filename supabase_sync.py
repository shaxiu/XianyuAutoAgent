"""
Supabase sync module for XianyuAutoAgent.
Handles:
- Reading config (API key, cookies, prompts) from Supabase
- Writing conversation records to Supabase
- Writing logs to Supabase
- Updating account status
"""

import os
import time
import threading
from datetime import datetime
from loguru import logger

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class SupabaseSync:
    """Syncs bot data with Supabase cloud database."""

    def __init__(self):
        self.enabled = False
        self.client: Client = None
        self.account_id = os.getenv("ACCOUNT_ID", "")
        self._log_buffer = []
        self._log_lock = threading.Lock()
        self._flush_interval = 5  # seconds
        self._last_flush = time.time()

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")

        if not SUPABASE_AVAILABLE:
            logger.warning("supabase package not installed, cloud sync disabled")
            return

        if not url or not key or not self.account_id:
            logger.info("Supabase env vars not set, cloud sync disabled")
            return

        try:
            self.client = create_client(url, key)
            self.enabled = True
            logger.info(f"Supabase sync enabled for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to init Supabase client: {e}")

    def get_account_config(self) -> dict:
        """Fetch account config from Supabase. Returns dict with keys:
        cookies_str, api_key, model_base_url, model_name
        Returns empty dict if disabled or error.
        """
        if not self.enabled:
            return {}
        try:
            result = (
                self.client.table("accounts")
                .select("*")
                .eq("id", self.account_id)
                .single()
                .execute()
            )
            return result.data or {}
        except Exception as e:
            logger.error(f"Failed to fetch account config: {e}")
            return {}

    def get_prompts(self) -> dict:
        """Fetch prompts from Supabase. Returns dict like:
        {"classify": "...", "price": "...", "tech": "...", "default": "..."}
        """
        if not self.enabled:
            return {}
        try:
            result = (
                self.client.table("prompts")
                .select("type, content")
                .eq("account_id", self.account_id)
                .execute()
            )
            return {row["type"]: row["content"] for row in (result.data or [])}
        except Exception as e:
            logger.error(f"Failed to fetch prompts: {e}")
            return {}

    def get_latest_cookies(self) -> str:
        """Fetch the latest cookies_str from Supabase for this account.
        Returns empty string if disabled or error.
        """
        if not self.enabled:
            return ""
        try:
            result = (
                self.client.table("accounts")
                .select("cookies_str")
                .eq("id", self.account_id)
                .single()
                .execute()
            )
            return (result.data or {}).get("cookies_str", "")
        except Exception as e:
            logger.error(f"Failed to fetch cookies from Supabase: {e}")
            return ""

    def update_cookies(self, cookies_str: str):
        """Update cookies_str in Supabase for this account."""
        if not self.enabled:
            return
        try:
            self.client.table("accounts").update(
                {"cookies_str": cookies_str}
            ).eq("id", self.account_id).execute()
        except Exception as e:
            logger.error(f"Failed to update cookies in Supabase: {e}")

    def update_status(self, status: str):
        """Update account status: online, offline, error"""
        if not self.enabled:
            return
        try:
            self.client.table("accounts").update(
                {"status": status}
            ).eq("id", self.account_id).execute()
        except Exception as e:
            logger.error(f"Failed to update status: {e}")

    def log_conversation(self, chat_id: str, item_id: str, item_title: str,
                         role: str, content: str, intent: str = None):
        """Write a conversation message to Supabase."""
        if not self.enabled:
            return
        try:
            self.client.table("conversations").insert({
                "account_id": self.account_id,
                "chat_id": chat_id,
                "item_id": item_id,
                "item_title": item_title or "",
                "role": role,
                "content": content,
                "intent": intent,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

    def buffer_log(self, level: str, message: str):
        """Buffer a log entry. Flushed every _flush_interval seconds."""
        if not self.enabled:
            return
        with self._log_lock:
            self._log_buffer.append({
                "account_id": self.account_id,
                "level": level,
                "message": message[:2000],  # truncate long messages
            })

    def flush_logs(self):
        """Flush buffered logs to Supabase."""
        if not self.enabled:
            return
        with self._log_lock:
            if not self._log_buffer:
                return
            batch = self._log_buffer.copy()
            self._log_buffer.clear()

        try:
            self.client.table("logs").insert(batch).execute()
        except Exception as e:
            logger.error(f"Failed to flush logs: {e}")

    def maybe_flush_logs(self):
        """Flush logs if enough time has passed."""
        now = time.time()
        if now - self._last_flush >= self._flush_interval:
            self.flush_logs()
            self._last_flush = now


# Global singleton
_sync_instance = None


def get_sync() -> SupabaseSync:
    """Get or create the global SupabaseSync instance."""
    global _sync_instance
    if _sync_instance is None:
        _sync_instance = SupabaseSync()
    return _sync_instance
