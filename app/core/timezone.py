from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def get_timezone() -> ZoneInfo:
    return ZoneInfo(settings.TIMEZONE)


def now_local() -> datetime:
    return datetime.now(get_timezone())


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=get_timezone())
    return dt.astimezone(get_timezone())


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def local_iso() -> str:
    return now_local().isoformat()


def local_folder_timestamp(value: datetime | str) -> str:
    dt = parse_datetime(value) if isinstance(value, str) else value
    return to_local(dt).strftime("%Y-%m-%d_%H-%M-%S")


def local_date_str() -> str:
    return now_local().strftime("%Y-%m-%d")
