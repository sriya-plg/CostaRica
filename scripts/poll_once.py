import logging

from app.core.logging import configure_logging
from app.jobs.email_poller import poll_new_emails
from app.persistence.processed_emails import init_db

configure_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    init_db()
    logger.info("Executing single manual email poll...")
    count = poll_new_emails()
    print(f"\nPoll completed successfully: {count} new email(s) processed.")
