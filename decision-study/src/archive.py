"""Immutable request/attempt archives with exclusive create."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import ATTEMPTS_DIR, RAW_DIR, REQUESTS_DIR


def exclusive_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(path), flags, 0o644)
    try:
        payload = (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
        os.write(fd, payload)
    finally:
        os.close(fd)


def save_request(request: dict[str, Any]) -> Path:
    path = REQUESTS_DIR / f"{request['request_id']}.json"
    exclusive_write_json(path, request)
    return path


def save_attempt(attempt: dict[str, Any]) -> Path:
    path = ATTEMPTS_DIR / f"{attempt['attempt_id']}.json"
    exclusive_write_json(path, attempt)
    return path


def save_raw(name: str, obj: Any) -> Path:
    path = RAW_DIR / name
    exclusive_write_json(path, obj)
    return path
