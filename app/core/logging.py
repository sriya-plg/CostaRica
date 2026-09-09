import json
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

# Log layout:
#   logs/
#     YYYY-MM-DD/
#       app.log    — all logs (INFO and above)
#       error.log  — ERROR and CRITICAL only
# A new dated folder is created on startup and automatically at midnight.


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class DailyFolderFileHandler(logging.Handler):
    """Write JSON logs to {log_dir}/{YYYY-MM-DD}/{filename}, rolling into a new folder at midnight."""

    def __init__(self, log_dir: str, filename: str, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._log_dir = Path(log_dir)
        self._filename = filename
        self._current_date: str | None = None
        self._stream = None
        self._lock = threading.Lock()

    def _path_for_date(self, date_str: str) -> Path:
        return self._log_dir / date_str / self._filename

    def prepare_for_today(self) -> None:
        """Create today's folder and open the log file (called at startup)."""
        with self._lock:
            self._open_stream_for_current_date()

    def _open_stream_for_current_date(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today == self._current_date and self._stream is not None:
            return
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        path = self._path_for_date(today)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = path.open("a", encoding="utf-8")
        self._current_date = today

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._open_stream_for_current_date()
                assert self._stream is not None
                self._stream.write(msg + "\n")
                self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            self._current_date = None
        super().close()


def configure_logging(level: int = logging.INFO) -> None:
    formatter = JsonFormatter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    app_file_handler = DailyFolderFileHandler(settings.LOG_DIR, "app.log", level=logging.INFO)
    app_file_handler.setFormatter(formatter)
    app_file_handler.prepare_for_today()

    error_file_handler = DailyFolderFileHandler(settings.LOG_DIR, "error.log", level=logging.ERROR)
    error_file_handler.setFormatter(formatter)
    error_file_handler.prepare_for_today()

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(app_file_handler)
    root.addHandler(error_file_handler)
    root.setLevel(level)
