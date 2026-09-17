from contextlib import contextmanager
import json
import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.timezone import local_iso

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS processed_emails (
    message_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    received_at TEXT NOT NULL,
    subject TEXT,
    shipment_number TEXT,
    invoice_number TEXT,
    result_json TEXT
)
"""


@contextmanager
def _get_db() -> Generator[sqlite3.Connection, None, None]:
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _get_db() as conn:
        conn.execute(_CREATE_TABLE)
        # Check and add columns if upgrading from older DB
        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(processed_emails)").fetchall()
        }
        for col, col_type in [
            ("subject", "TEXT"),
            ("shipment_number", "TEXT"),
            ("invoice_number", "TEXT"),
            ("result_json", "TEXT"),
        ]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE processed_emails ADD COLUMN {col} {col_type}")
        conn.commit()


def get_processed_email(message_id: str) -> sqlite3.Row | None:
    with _get_db() as conn:
        row = conn.execute(
            """
            SELECT message_id, status, received_at, subject, shipment_number, invoice_number, result_json 
            FROM processed_emails WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
    return row


def insert_processed_email(message_id: str, status: str = "received") -> bool:
    """Insert a new row. Returns True if inserted, False if duplicate."""
    received_at = local_iso()
    with _get_db() as conn:
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
    with _get_db() as conn:
        conn.execute(
            "UPDATE processed_emails SET status = ? WHERE message_id = ?",
            (status, message_id),
        )
        conn.commit()


def update_processed_email_results(
    message_id: str,
    status: str,
    subject: str | None = None,
    shipment_number: str | None = None,
    invoice_number: str | None = None,
    result_data: dict[str, Any] | None = None,
) -> None:
    """Update processing status, subject, extracted shipment & invoice numbers, and full result JSON."""
    result_json_str = json.dumps(result_data, indent=2) if result_data is not None else None
    with _get_db() as conn:
        conn.execute(
            """
            UPDATE processed_emails 
            SET status = ?, subject = ?, shipment_number = ?, invoice_number = ?, result_json = ? 
            WHERE message_id = ?
            """,
            (status, subject, shipment_number, invoice_number, result_json_str, message_id),
        )
        conn.commit()
