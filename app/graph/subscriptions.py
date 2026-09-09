import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.graph.client import graph_client
from app.persistence.subscription_store import SubscriptionState, save_subscription

logger = logging.getLogger(__name__)

MESSAGES_MAX_TTL_MINUTES = 4230
CREATE_MAX_ATTEMPTS = 3
CREATE_RETRY_DELAY_SECONDS = 5


class WebhookNotReachableError(RuntimeError):
    """Raised when the webhook is not reachable locally or via the public tunnel URL."""


def _max_expiration() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=MESSAGES_MAX_TTL_MINUTES)


def _to_graph_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _state_from_response(data: dict) -> SubscriptionState:
    return SubscriptionState(
        id=data["id"],
        expiration_datetime=data["expirationDateTime"],
        client_state=settings.CLIENT_STATE,
    )


def _is_retryable_validation_error(exc: httpx.HTTPStatusError) -> bool:
    text = exc.response.text.lower()
    return any(
        phrase in text
        for phrase in (
            "validation request timed out",
            "badgateway",
            "validation request failed",
        )
    )


def verify_webhook_reachable() -> None:
    """Confirm local app and public tunnel URL respond before calling Graph."""
    local_url = f"http://127.0.0.1:{settings.APP_PORT}/webhook"
    params = {"validationToken": "warmup"}

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(local_url, params=params)
        if response.status_code != 200 or response.text != "warmup":
            raise WebhookNotReachableError(
                f"Local webhook at {local_url} returned {response.status_code!r}, expected 200 + token"
            )
        logger.info("Local webhook OK at %s", local_url)
    except httpx.HTTPError as exc:
        raise WebhookNotReachableError(
            f"Local webhook at {local_url} is not reachable — is uvicorn running on port {settings.APP_PORT}? {exc}"
        ) from exc

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(settings.NOTIFICATION_URL, params=params)
        if response.status_code != 200 or response.text != "warmup":
            raise WebhookNotReachableError(
                f"Public webhook at {settings.NOTIFICATION_URL} returned {response.status_code!r}, expected 200 + token"
            )
        logger.info("Public webhook OK at %s", settings.NOTIFICATION_URL)
    except httpx.HTTPError as exc:
        raise WebhookNotReachableError(
            f"Public webhook at {settings.NOTIFICATION_URL} is not reachable — "
            f"start ngrok (`ngrok http {settings.APP_PORT}`) and set NOTIFICATION_URL in .env to the "
            f"current HTTPS URL + /webhook. Error: {exc}"
        ) from exc


def _create_subscription_once() -> SubscriptionState:
    expiration = _max_expiration()
    payload = {
        "changeType": "created",
        "notificationUrl": settings.NOTIFICATION_URL,
        "resource": f"/users/{settings.MAILBOX}/mailFolders('Inbox')/messages",
        "expirationDateTime": _to_graph_datetime(expiration),
        "clientState": settings.CLIENT_STATE,
    }
    logger.info("Creating Graph subscription for mailbox %s", settings.MAILBOX)
    data = graph_client.request("POST", "/subscriptions", json=payload)
    state = _state_from_response(data)
    save_subscription(state)
    logger.info(
        "Created subscription %s expiring %s",
        state.id,
        state.expiration_datetime,
    )
    return state


def create_subscription() -> SubscriptionState:
    verify_webhook_reachable()
    last_error: httpx.HTTPStatusError | None = None

    for attempt in range(1, CREATE_MAX_ATTEMPTS + 1):
        try:
            return _create_subscription_once()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if attempt >= CREATE_MAX_ATTEMPTS or not _is_retryable_validation_error(exc):
                raise
            logger.warning(
                "Subscription validation not ready (attempt %s/%s), retrying in %ss",
                attempt,
                CREATE_MAX_ATTEMPTS,
                CREATE_RETRY_DELAY_SECONDS,
            )
            time.sleep(CREATE_RETRY_DELAY_SECONDS)
            verify_webhook_reachable()

    if last_error:
        raise last_error
    raise RuntimeError("Subscription creation failed without a captured error")


def delete_subscription(subscription_id: str) -> None:
    logger.info("Deleting Graph subscription %s", subscription_id)
    graph_client.request("DELETE", f"/subscriptions/{subscription_id}")


def renew_subscription(subscription_id: str) -> SubscriptionState:
    expiration = _max_expiration()
    payload = {"expirationDateTime": _to_graph_datetime(expiration)}
    logger.info("Renewing Graph subscription %s", subscription_id)
    data = graph_client.request(
        "PATCH",
        f"/subscriptions/{subscription_id}",
        json=payload,
    )
    state = _state_from_response(data)
    save_subscription(state)
    logger.info(
        "Renewed subscription %s expiring %s",
        state.id,
        state.expiration_datetime,
    )
    return state
