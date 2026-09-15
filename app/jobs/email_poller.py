import logging
import threading
from typing import Any

from app.core.config import settings
from app.graph.messages import list_unread_emails, mark_message_as_read
from app.persistence.processed_emails import get_processed_email, insert_processed_email
from app.pipeline.message_processor import process_new_message

logger = logging.getLogger(__name__)


class EmailTracker:
    """Thread-safe in-flight tracker to prevent concurrent processing of the same email."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

    def is_in_flight(self, message_id: str) -> bool:
        with self._lock:
            return message_id in self._in_flight

    def start(self, message_id: str) -> bool:
        with self._lock:
            if message_id in self._in_flight:
                return False
            self._in_flight.add(message_id)
            return True

    def complete(self, message_id: str) -> None:
        with self._lock:
            self._in_flight.discard(message_id)


tracker = EmailTracker()


def process_one_email(message: dict[str, Any]) -> bool:
    """Process a single unread email and mark as read upon successful completion."""
    message_id = message.get("id")
    if not message_id:
        return False

    # Check if already processed in database
    existing_row = get_processed_email(message_id)
    if existing_row and existing_row["status"] == "processed":
        logger.info("Message %s already processed in DB; ensuring isRead=true in Outlook", message_id)
        try:
            mark_message_as_read(message_id)
        except Exception as exc:
            logger.warning("Could not mark duplicate message %s as read: %s", message_id, exc)
        return False

    # Acquire reservation
    if not tracker.start(message_id):
        logger.debug("Message %s is already in-flight, skipping", message_id)
        return False

    try:
        insert_processed_email(message_id, status="received")
        logger.info(
            "Starting processing for unread email message_id=%s subject=%r",
            message_id,
            message.get("subject"),
        )
        process_new_message(message_id)

        # Disposition: Success -> Mark isRead=true in Outlook
        try:
            mark_message_as_read(message_id)
        except Exception as exc:
            logger.warning("Could not mark message %s as read in Graph: %s", message_id, exc)

        return True

    except Exception as exc:
        logger.exception(
            "Failed to process email message_id=%s. Leaving unread in Outlook for retry. Error: %s",
            message_id,
            exc,
        )
        return False

    finally:
        tracker.complete(message_id)


def poll_new_emails() -> int:
    """Poll Microsoft Graph for unread emails within the lookback window.

    Returns:
        Number of successfully processed emails in this cycle.
    """
    logger.debug("Polling Inbox for unread emails (lookback: %dh)...", settings.INITIAL_LOOKBACK_HOURS)

    try:
        unread_emails = list_unread_emails(settings.INITIAL_LOOKBACK_HOURS)
    except Exception as exc:
        logger.error("Failed to query unread emails from Graph API: %s", exc)
        return 0

    if not unread_emails:
        return 0

    logger.info("Found %d unread email(s) to process", len(unread_emails))

    processed_count = 0
    for message in unread_emails:
        if process_one_email(message):
            processed_count += 1

    logger.info("Batch complete: %d email(s) processed & marked as read", processed_count)
    return processed_count
