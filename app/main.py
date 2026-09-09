import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.core.logging import configure_logging
from app.graph.subscriptions import WebhookNotReachableError
from app.jobs.subscription_lifecycle import (
    ensure_valid_subscription,
    ensure_valid_subscription_at_startup,
    renew_if_needed,
)
from app.persistence.processed_emails import init_db
from app.persistence.subscription_store import load_subscription
from app.webhook.router import router as webhook_router

configure_logging()
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


async def _try_create_subscription() -> None:
    """Create subscription after startup if missing and ngrok/webhook is reachable."""
    await asyncio.sleep(5)
    if load_subscription() is not None:
        return
    try:
        await asyncio.to_thread(ensure_valid_subscription)
    except WebhookNotReachableError as exc:
        logger.warning(
            "Subscription not created — webhook not reachable: %s. "
            "Start ngrok, set NOTIFICATION_URL in .env, then run: "
            "python scripts/create_subscription.py",
            exc,
        )
    except Exception:
        logger.exception(
            "Subscription creation failed. Run: python scripts/create_subscription.py"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_valid_subscription_at_startup()
    scheduler.add_job(renew_if_needed, "interval", hours=4, id="renew_subscription")
    scheduler.start()
    create_task = asyncio.create_task(_try_create_subscription())
    logger.info("Application startup complete")
    yield
    create_task.cancel()
    scheduler.shutdown(wait=False)
    logger.info("Application shutdown complete")


app = FastAPI(title="Costa Rica Graph Webhook", lifespan=lifespan)
app.include_router(webhook_router)
