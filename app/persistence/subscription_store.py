import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import settings


@dataclass
class SubscriptionState:
    id: str
    expiration_datetime: str
    client_state: str

    @property
    def expiration(self) -> datetime:
        return datetime.fromisoformat(self.expiration_datetime.replace("Z", "+00:00"))


def _subscription_path() -> Path:
    path = Path(settings.SUBSCRIPTION_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_subscription() -> SubscriptionState | None:
    path = _subscription_path()
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return SubscriptionState(**data)


def save_subscription(state: SubscriptionState) -> None:
    path = _subscription_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(state), f, indent=2)
