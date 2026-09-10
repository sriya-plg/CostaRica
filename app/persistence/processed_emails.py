import sqlite3
from pathlib import Path

from app.core.config import settings
from app.core.timezone import local_iso

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS processed_emails (
    message_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    received_at TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_CREATE_TABLE)
        conn.commit()


def get_processed_email(message_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT message_id, status, received_at FROM processed_emails WHERE message_id = ?",
            (message_id,),
        ).fetchone()
    return row


def insert_processed_email(message_id: str, status: str = "received") -> bool:
    """Insert a new row. Returns True if inserted, False if duplicate."""
    received_at = local_iso()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO processed_emails (message_id, status, received_at)
            VALUES (?, ?, ?)
            ON CONFLICT(message_id) DO NOTHING
            """,
            (message_id, status, received_at),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_processed_email_status(message_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE processed_emails SET status = ? WHERE message_id = ?",
            (status, message_id),
        )
        conn.commit()
