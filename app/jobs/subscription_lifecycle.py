import logging
from datetime import datetime, timedelta, timezone

from app.graph.subscriptions import create_subscription, renew_subscription
from app.persistence.subscription_store import SubscriptionState, load_subscription

logger = logging.getLogger(__name__)

RENEW_WITHIN = timedelta(days=1)


def is_expired(state: SubscriptionState) -> bool:
    return state.expiration <= datetime.now(timezone.utc)


def needs_renewal(state: SubscriptionState) -> bool:
    return state.expiration <= datetime.now(timezone.utc) + RENEW_WITHIN


def _needs_create(state: SubscriptionState | None) -> bool:
    return state is None or is_expired(state)


def ensure_valid_subscription_at_startup() -> None:
    """Renew an existing subscription on startup. Creation is deferred."""
    state = load_subscription()
    if _needs_create(state):
        logger.info(
            "Subscription missing or expired — will create after the server is listening"
        )
        return

    if needs_renewal(state):
        logger.info("Subscription %s nearing expiry, renewing on startup", state.id)
        renew_subscription(state.id)
        return

    logger.info(
        "Subscription %s valid until %s",
        state.id,
        state.expiration_datetime,
    )


def ensure_valid_subscription() -> SubscriptionState | None:
    """Create or renew as needed. Requires the webhook endpoint to be reachable."""
    state = load_subscription()
    if _needs_create(state):
        if state is None:
            logger.info("No subscription file found, creating subscription")
        else:
            logger.info("Subscription %s expired, creating new subscription", state.id)
        return create_subscription()

    if needs_renewal(state):
        logger.info("Subscription %s nearing expiry, renewing", state.id)
        return renew_subscription(state.id)

    logger.info(
        "Subscription %s valid until %s",
        state.id,
        state.expiration_datetime,
    )
    return state


def renew_if_needed() -> None:
    state = load_subscription()
    if state is None:
        logger.warning("No subscription on disk during renewal job, creating")
        create_subscription()
        return
    if needs_renewal(state):
        renew_subscription(state.id)
    else:
        logger.info(
            "Subscription %s does not need renewal yet (expires %s)",
            state.id,
            state.expiration_datetime,
        )
