"""Create (or recreate) a Microsoft Graph mail subscription and persist state."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import configure_logging
from app.graph.subscriptions import WebhookNotReachableError, create_subscription

if __name__ == "__main__":
    configure_logging()
    try:
        state = create_subscription()
    except WebhookNotReachableError as exc:
        print(f"Webhook not ready: {exc}")
        raise SystemExit(1) from exc
    print(f"Subscription created: id={state.id} expires={state.expiration_datetime}")
