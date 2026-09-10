import base64
import os
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.timezone import local_folder_timestamp

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_PATH_LEN = 250


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", name).strip(" .")
    return cleaned or "attachment"


def _email_folder_name(received_at: str) -> str:
    return local_folder_timestamp(received_at)


def make_email_download_dir(received_at: str) -> Path:
    base_name = _email_folder_name(received_at)
    dest_dir = Path(settings.ATTACHMENTS_DIR) / base_name
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir
    for index in range(2, 1000):
        candidate = Path(settings.ATTACHMENTS_DIR) / f"{base_name}_{index}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
    raise RuntimeError(f"Could not find unique download folder for {base_name}")


def _windows_extended_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    resolved = path.resolve()
    path_str = str(resolved)
    if path_str.startswith("\\\\?\\") or len(path_str) < _MAX_PATH_LEN:
        return resolved
    if resolved.drive:
        return Path("\\\\?\\" + path_str)
    return resolved


def _truncate_filename(name: str, dest_dir: Path) -> str:
    base_len = len(str(dest_dir.resolve())) + 1
    max_filename = max(20, _MAX_PATH_LEN - base_len)
    if len(name) <= max_filename:
        return name
    path = Path(name)
    suffix = path.suffix
    stem = _safe_filename(path.stem or "attachment")
    stem_budget = max(10, max_filename - len(suffix))
    if len(stem) > stem_budget:
        stem = stem[: max(1, stem_budget - 3)] + "..."
    return f"{stem}{suffix}"


def _unique_path(dest_dir: Path, filename: str) -> Path:
    path = dest_dir / filename
    if not path.exists():
        return path
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(2, 1000):
        candidate = dest_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique path for {filename} in {dest_dir}")


def save_attachment(attachment: dict[str, Any], dest_dir: Path) -> Path:
    name = _safe_filename(attachment.get("name", "attachment"))
    content_bytes = attachment.get("contentBytes")
    if not content_bytes:
        raise ValueError(f"Attachment {attachment.get('id')} has no contentBytes")

    filename = _truncate_filename(name, dest_dir)
    dest_path = _unique_path(dest_dir, filename)
    _windows_extended_path(dest_path).write_bytes(base64.b64decode(content_bytes))
    return dest_path
