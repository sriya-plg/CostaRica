from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from app.core.config import settings
from app.graph.client import graph_client

logger = logging.getLogger(__name__)


def list_unread_emails(lookback_hours: int | None = None) -> list[dict[str, Any]]:
    """Fetch unread emails within the lookback time window from Microsoft Graph.

    Args:
        lookback_hours: Number of hours to look back (defaults to settings.INITIAL_LOOKBACK_HOURS).

    Returns:
        List of unread email dictionaries.
    """
    hours = lookback_hours if lookback_hours is not None else settings.INITIAL_LOOKBACK_HOURS
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    filter_query = f"isRead eq false and receivedDateTime ge {cutoff_iso}"
    select_fields = "id,subject,receivedDateTime,hasAttachments,from,isRead"
    url = (
        f"/users/{settings.MAILBOX}/mailFolders('Inbox')/messages"
        f"?$filter={filter_query}&$select={select_fields}&$top=50&$orderby=receivedDateTime asc"
    )

    logger.debug("Querying unread emails with filter: %s", filter_query)

    unread_emails: list[dict[str, Any]] = []
    current_url: str | None = url

    while current_url:
        data = graph_client.request("GET", current_url)
        messages = data.get("value", [])
        unread_emails.extend(messages)
        current_url = data.get("@odata.nextLink")

    return unread_emails


def mark_message_as_read(message_id: str) -> None:
    """Mark an email as read in Microsoft Graph so it is not processed again."""
    path = f"/users/{settings.MAILBOX}/messages/{message_id}"
    logger.debug("Marking message_id=%s as isRead=true in Graph", message_id)
    graph_client.request("PATCH", path, json={"isRead": True})


def get_message_details(message_id: str) -> dict[str, Any]:
    """Fetch email details such as subject, sender, and received time from Microsoft Graph."""
    path = f"/users/{settings.MAILBOX}/messages/{message_id}?$select=id,subject,receivedDateTime,hasAttachments,from,isRead"
    logger.debug("Fetching message details for message_id=%s", message_id)
    return graph_client.request("GET", path)

