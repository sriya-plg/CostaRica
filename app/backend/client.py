import logging
from typing import Any

logger = logging.getLogger(__name__)


def report_attachment_details(message_id: str, attachment_meta: dict[str, Any]) -> None:
    # Stub: logs downloaded attachment details
    logger.info(
        "Stub report_attachment_details message_id=%s meta=%s",
        message_id,
        attachment_meta,
    )


def report_shipment_invoice(payload: dict[str, Any]) -> None:
    """
    Downstream integration hook for extracted shipment & invoice data.
    Ready to make an HTTP POST request to your ML Order Entry / backend API once the contract is ready.
    """
    logger.info(
        "Extracted Shipment & Invoice payload for message_id=%s: %s",
        payload.get("message_id"),
        payload,
    )
    # TODO: Hit downstream backend API when endpoint is configured
    # Example:
    # httpx.post(settings.BACKEND_API_URL, json=payload, timeout=10.0)
