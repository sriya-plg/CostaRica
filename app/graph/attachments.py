import logging
from typing import Any

from app.core.config import settings
from app.graph.client import graph_client

logger = logging.getLogger(__name__)

FILE_ATTACHMENT_TYPE = "#microsoft.graph.fileAttachment"
ITEM_ATTACHMENT_TYPE = "#microsoft.graph.itemAttachment"


def _attachments_path(message_id: str) -> str:
    return f"/users/{settings.MAILBOX}/messages/{message_id}/attachments"


def _fetch_file_attachment(message_id: str, attachment_id: str) -> dict[str, Any]:
    return graph_client.request(
        "GET",
        f"{_attachments_path(message_id)}/{attachment_id}",
    )


def get_attachments(message_id: str) -> list[dict[str, Any]]:
    data = graph_client.request("GET", _attachments_path(message_id))
    file_attachments: list[dict[str, Any]] = []

    for attachment in data.get("value", []):
        odata_type = attachment.get("@odata.type", "")
        if odata_type == ITEM_ATTACHMENT_TYPE:
            logger.info(
                "Skipping itemAttachment id=%s name=%s for message_id=%s",
                attachment.get("id"),
                attachment.get("name"),
                message_id,
            )
            continue
        if odata_type != FILE_ATTACHMENT_TYPE:
            logger.warning(
                "Skipping unknown attachment type %s id=%s for message_id=%s",
                odata_type,
                attachment.get("id"),
                message_id,
            )
            continue

        if not attachment.get("contentBytes"):
            attachment = _fetch_file_attachment(message_id, attachment["id"])
        file_attachments.append(attachment)

    return file_attachments
