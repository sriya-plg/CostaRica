import logging
from typing import Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CoreDataClient:
    """Client for Pegasus Core Data Order Entry APIs."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.CORE_DATA_BASE_URL).rstrip("/")

    def add_email_log(
        self,
        email: str,
        email_subject: str,
        email_body: str,
        email_received_on: str,
        attachment_filenames: list[str],
    ) -> int | None:
        """
        POST /AddCoreDataEmailLog
        Logs the incoming email and attachment metadata in Core Data database.
        Returns the created emailLogId if successful.
        """
        url = f"{self.base_url}/AddCoreDataEmailLog"
        payload = {
            "email": email or "",
            "emailSubject": email_subject or "",
            "emailBody": email_body or "",
            "emailReceivedOn": email_received_on,
            "attachments": [
                {"attachmentId": 0, "fileName": filename}
                for filename in attachment_filenames
            ],
        }

        logger.info(
            "Calling AddCoreDataEmailLog: url=%s email=%s subject=%r attachments_count=%d",
            url,
            email,
            email_subject,
            len(attachment_filenames),
        )

        try:
            resp = httpx.post(url, json=payload, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info("AddCoreDataEmailLog response: %s", data)

            if isinstance(data, dict):
                log_id = data.get("emailLogId") or data.get("id") or data.get("data")
                return int(log_id) if log_id is not None else None
            elif isinstance(data, (int, str)) and str(data).isdigit():
                return int(data)
            return None
        except Exception as exc:
            logger.error("Failed to execute AddCoreDataEmailLog: %s", exc)
            return None

    def get_attachment_list(self, email_log_id: int | str) -> list[dict[str, Any]]:
        """
        GET /GetCoreDataAttachmentList/{emailLogId}
        Retrieves the list of attachments associated with the email log.
        Returns: list of dicts with 'attachmentId' and 'fileName'.
        """
        url = f"{self.base_url}/GetCoreDataAttachmentList/{email_log_id}"
        logger.info("Calling GetCoreDataAttachmentList: url=%s", url)

        try:
            resp = httpx.get(url, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info("GetCoreDataAttachmentList response for emailLogId=%s: %s", email_log_id, data)

            if isinstance(data, dict):
                return data.get("attachments", [])
            elif isinstance(data, list):
                return data
            return []
        except Exception as exc:
            logger.error(
                "Failed to execute GetCoreDataAttachmentList for emailLogId=%s: %s",
                email_log_id,
                exc,
            )
            return []

    def add_activity(
        self,
        email_log_id: int,
        attachment_id: int,
        bill_to: int | None = None,
    ) -> dict[str, Any] | None:
        """
        POST /AddCoreDataActivity
        Creates an activity associated with an email log and attachment.
        """
        url = f"{self.base_url}/AddCoreDataActivity"
        bill_to_val = bill_to if bill_to is not None else settings.CORE_DATA_BILL_TO
        payload = {
            "emailLogId": email_log_id,
            "attachmentId": attachment_id,
            "billTo": bill_to_val,
        }

        logger.info("Calling AddCoreDataActivity: url=%s payload=%s", url, payload)

        try:
            resp = httpx.post(url, json=payload, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info("AddCoreDataActivity response: %s", data)
            return data if isinstance(data, dict) else {"response": data}
        except Exception as exc:
            logger.error(
                "Failed to execute AddCoreDataActivity for emailLogId=%s, attachmentId=%s: %s",
                email_log_id,
                attachment_id,
                exc,
            )
            return None


core_data_client = CoreDataClient()


def report_attachment_details(message_id: str, attachment_meta: dict[str, Any]) -> None:
    """Logs downloaded attachment details."""
    logger.info(
        "Stub report_attachment_details message_id=%s meta=%s",
        message_id,
        attachment_meta,
    )


def report_shipment_invoice(payload: dict[str, Any]) -> None:
    """
    Downstream integration hook for extracted shipment & invoice data.
    """
    logger.info(
        "Extracted Shipment & Invoice payload for message_id=%s: %s",
        payload.get("message_id"),
        payload,
    )
