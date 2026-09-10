import logging
from typing import Any

logger = logging.getLogger(__name__)


def report_attachment_details(message_id: str, attachment_meta: dict[str, Any]) -> None:
    # TODO: POST attachment metadata to backend once API contract is confirmed
    logger.info(
        "Stub report_attachment_details message_id=%s meta=%s",
        message_id,
        attachment_meta,
    )
