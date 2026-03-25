from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import KVSetting


KV_KEY = "sensors"


def load_sensors(db: Session) -> list[dict[str, Any]]:
    row = db.get(KVSetting, KV_KEY)
    if not row or not row.value:
        return []
    try:
        data = json.loads(row.value)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def save_sensors(db: Session, sensors: list[dict[str, Any]]) -> None:
    text = json.dumps(sensors)
    row = db.get(KVSetting, KV_KEY)
    if row:
        row.value = text
    else:
        db.add(KVSetting(key=KV_KEY, value=text))
    db.commit()

