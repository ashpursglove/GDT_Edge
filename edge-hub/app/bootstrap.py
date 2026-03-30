"""
Apply optional environment defaults into SQLite hub settings when fields are still empty.

Used for Docker / scripted installs so operators can set GDT_CONSOLE_API_* once and open the UI
with fields already filled. Does not overwrite values the user saved in the UI.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas import HubSettings
from app.services.settings_store import load_hub_settings, save_hub_settings

logger = logging.getLogger(__name__)


def apply_env_preseed_if_needed(db: Session) -> None:
    """Merge GDT_CONSOLE_* / GDT_SERIAL_DEVICE into hub settings only for empty fields."""
    current = load_hub_settings(db)
    url = (settings.console_api_base_url or "").strip()
    key = (settings.console_api_key or "").strip()
    serial = (settings.serial_device or "").strip()

    if not url and not key and not serial:
        return

    data = current.model_dump()
    changed = False

    if url and not (current.api_base_url or "").strip():
        data["api_base_url"] = url
        changed = True
    if key and not (current.api_key or "").strip():
        data["api_key"] = key
        changed = True
    if serial and not (current.serial_port or "").strip():
        data["serial_port"] = serial
        changed = True

    if not changed:
        return

    save_hub_settings(db, HubSettings.model_validate(data))
    logger.info(
        "Applied hub defaults from environment (empty fields only): "
        "console URL/key and/or serial port."
    )
