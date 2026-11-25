import logging
import threading
from typing import Any

from app.core.config import settings
from app.graph.messages import list_unread_emails, mark_message_as_read, send_alert_email
from app.pipeline.message_processor import process_new_message

logger = logging.getLogger(__name__)


class EmailTracker:
    """Thread-safe in-flight and retry tracker for email processing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()
        self._failures: dict[str, int] = {}

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

    def record_failure(self, message_id: str) -> int:
        with self._lock:
            count = self._failures.get(message_id, 0) + 1
            self._failures[message_id] = count
            return count

    def clear_failures(self, message_id: str) -> None:
        with self._lock:
            self._failures.pop(message_id, None)


tracker = EmailTracker()


def _extract_sender_address(message: dict[str, Any]) -> str:
    sender_info = message.get("from")
    if isinstance(sender_info, dict):
        return sender_info.get("emailAddress", {}).get("address", "") or ""
    return ""


def process_one_email(message: dict[str, Any]) -> bool:
    """Process a single unread email and manage read/retry/alert disposition."""
    message_id = message.get("id")
    if not message_id:
        return False

    # Acquire atomic reservation
    if not tracker.start(message_id):
        logger.debug("Message %s is already in-flight, skipping", message_id)
        return False

    try:
        logger.info(
            "Processing unread email [%s...] Subject: %r",
            message_id[:16],
            message.get("subject"),
        )
        process_new_message(message_id, received_at=message.get("receivedDateTime"))
        tracker.clear_failures(message_id)

        # Disposition: Success -> Mark isRead=true in Outlook
        try:
            mark_message_as_read(message_id)
        except Exception as exc:
            logger.warning("Could not mark message %s as read in Graph: %s", message_id, exc)

        return True

    except Exception as exc:
        failure_count = tracker.record_failure(message_id)
        max_attempts = 1 + settings.MAX_EMAIL_RETRIES

        if failure_count == 1:
            try:
                send_alert_email(
                    message_id=message_id,
                    subject=message.get("subject"),
                    reason=str(exc),
                    sender=_extract_sender_address(message),
                    received_at=message.get("receivedDateTime"),
                )
            except Exception as alert_exc:
                logger.error(
                    "Failed to send alert email for message_id=%s: %s",
                    message_id,
                    alert_exc,
                )

        if failure_count >= max_attempts:
            logger.error(
                "Email message_id=%s failed %d/%d attempt(s). Marking as read to stop retries. Error: %s",
                message_id,
                failure_count,
                max_attempts,
                exc,
            )
            try:
                mark_message_as_read(message_id)
                tracker.clear_failures(message_id)
            except Exception as mark_exc:
                logger.warning("Could not mark message %s as read in Graph: %s", message_id, mark_exc)
        else:
            retries_remaining = max_attempts - failure_count
            logger.exception(
                "Failed to process email message_id=%s (attempt %d/%d, %d retry(s) remaining). Leaving unread in Outlook. Error: %s",
                message_id,
                failure_count,
                max_attempts,
                retries_remaining,
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
