import logging
from typing import Any

from app.core.config import settings
from app.persistence.processed_emails import get_processed_email, insert_processed_email
from app.pipeline.message_processor import process_new_message

logger = logging.getLogger(__name__)


def handle_notification(notification: dict[str, Any]) -> None:
    client_state = notification.get("clientState")
    if client_state != settings.CLIENT_STATE:
        logger.warning("Rejected notification with invalid clientState")
        return

    resource_data = notification.get("resourceData") or {}
    message_id = resource_data.get("id")
    if not message_id:
        logger.warning("Notification missing resourceData.id: %s", notification)
        return

    if get_processed_email(message_id) is not None:
        logger.info("Duplicate notification for message_id=%s, skipping", message_id)
        return

    if not insert_processed_email(message_id, status="received"):
        logger.info(
            "Concurrent duplicate for message_id=%s, skipping after insert race",
            message_id,
        )
        return

    logger.info("Recorded new message message_id=%s", message_id)
    process_new_message(message_id)
