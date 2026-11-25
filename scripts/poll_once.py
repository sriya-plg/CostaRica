import logging
from pathlib import Path
import sys

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.logging import configure_logging
from app.jobs.email_poller import poll_new_emails

configure_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Executing single manual email poll...")
    count = poll_new_emails()
    print(f"\nPoll completed successfully: {count} new email(s) processed.")
