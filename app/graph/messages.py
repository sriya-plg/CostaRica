import logging
from typing import Any

from app.core.config import settings
from app.graph.client import graph_client

logger = logging.getLogger(__name__)


def get_message_details(message_id: str) -> dict[str, Any]:
    """Fetch email details such as subject, sender, and received time from Microsoft Graph."""
    path = f"/users/{settings.MAILBOX}/messages/{message_id}?$select=id,subject,receivedDateTime,hasAttachments,from"
    logger.info("Fetching message details for message_id=%s", message_id)
    return graph_client.request("GET", path)
