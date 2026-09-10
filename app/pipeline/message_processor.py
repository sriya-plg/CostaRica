import logging
from typing import Any

from app.backend.client import report_attachment_details
from app.graph.attachments import get_attachments
from app.persistence.processed_emails import get_processed_email, update_processed_email_status
from app.storage.attachments import make_email_download_dir, save_attachment

logger = logging.getLogger(__name__)


def _attachment_meta(attachment: dict[str, Any], saved_path: str) -> dict[str, Any]:
    return {
        "attachment_id": attachment["id"],
        "filename": attachment.get("name"),
        "content_type": attachment.get("contentType"),
        "size": attachment.get("size"),
        "saved_path": saved_path,
    }


def process_new_message(message_id: str) -> None:
    row = get_processed_email(message_id)
    if row is None:
        logger.error("message_id=%s not found in processed_emails", message_id)
        return

    received_at = row["received_at"]
    attachments = get_attachments(message_id)
    if not attachments:
        update_processed_email_status(message_id, "no_attachments")
        logger.info("message_id=%s has no file attachments", message_id)
        return

    dest_dir = make_email_download_dir(received_at)
    downloaded = 0
    for attachment in attachments:
        saved_path = save_attachment(attachment, dest_dir)
        report_attachment_details(message_id, _attachment_meta(attachment, str(saved_path)))
        downloaded += 1

    update_processed_email_status(message_id, "downloaded")
    logger.info(
        "message_id=%s downloaded %s attachment(s) to %s",
        message_id,
        downloaded,
        dest_dir,
    )
