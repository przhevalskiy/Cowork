"""Load Google service-account credentials from env (JSON string or file path)."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings


def load_service_account_info() -> dict:
    settings = get_settings()
    raw = settings.google_credentials_json.strip()
    if not raw and settings.google_credentials_file:
        path = Path(settings.google_credentials_file).expanduser()
        if not path.is_file():
            raise RuntimeError(f"GOOGLE_CREDENTIALS_FILE not found: {path}")
        raw = path.read_text()
    if not raw:
        raise RuntimeError(
            "Google credentials not configured — set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE"
        )
    return json.loads(raw)
