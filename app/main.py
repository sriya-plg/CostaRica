import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging
from app.jobs.email_poller import poll_new_emails

configure_logging()
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _scheduled_poll_job() -> None:
    try:
        poll_new_emails()
    except Exception as exc:
        logger.exception("Error during scheduled email poll: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Start background polling scheduler
    scheduler.add_job(
        _scheduled_poll_job,
        "interval",
        seconds=settings.POLL_INTERVAL_SECONDS,
        id="email_unread_poller",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Started background email poller with interval=%ss, lookback=%sh",
        settings.POLL_INTERVAL_SECONDS,
        settings.INITIAL_LOOKBACK_HOURS,
    )

    # Trigger an immediate first poll in the background after startup
    asyncio.create_task(asyncio.to_thread(_scheduled_poll_job))

    logger.info("Application startup complete")
    yield

    scheduler.shutdown(wait=False)
    logger.info("Application shutdown complete")


app = FastAPI(title="Costa Rica Email Poller", lifespan=lifespan)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "costa-rica-email-poller"}


@app.get("/status")
def status():
    return {
        "poll_interval_seconds": settings.POLL_INTERVAL_SECONDS,
        "lookback_hours": settings.INITIAL_LOOKBACK_HOURS,
        "mailbox": settings.MAILBOX,
    }


@app.post("/poll")
def trigger_poll():
    """Manually trigger a poll iteration on-demand."""
    count = poll_new_emails()
    return {"status": "success", "processed_count": count}


