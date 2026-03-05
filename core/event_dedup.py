import os
import sqlite3
import time

try:
    from loguru import logger
except Exception:  # pragma: no cover - fallback for minimal test env
    import logging

    logger = logging.getLogger(__name__)


class EventDedupStore:
    def __init__(self, db_path="data/chat_history.db", ttl_seconds=None):
        self.db_path = db_path
        self.ttl_seconds = int(ttl_seconds if ttl_seconds is not None else 86400)
        self._init_db()

    def _init_db(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at
            ON processed_events(processed_at)
            """
        )
        conn.commit()
        conn.close()

    def is_duplicate(self, event_id):
        if not isinstance(event_id, str) or not event_id:
            return False

        now = int(time.time())
        self.cleanup_expired(now)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            if cursor.fetchone():
                return True

            cursor.execute(
                "INSERT INTO processed_events (event_id, processed_at) VALUES (?, ?)",
                (event_id, now),
            )
            conn.commit()
            return False
        except sqlite3.IntegrityError:
            return True
        except Exception as exc:
            logger.warning(f"event dedup lookup failed event_id={event_id} err={exc}")
            return False
        finally:
            conn.close()

    def cleanup_expired(self, now_ts=None):
        current = int(now_ts if now_ts is not None else time.time())
        expire_before = current - max(self.ttl_seconds, 0)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM processed_events WHERE processed_at < ?",
                (expire_before,),
            )
            conn.commit()
        except Exception as exc:
            logger.warning(f"event dedup cleanup failed: {exc}")
        finally:
            conn.close()

