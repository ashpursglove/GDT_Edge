from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import KVSetting
from app.schemas import HubSettings

KV_KEY = "hub"


def load_hub_settings(db: Session) -> HubSettings:
    row = db.get(KVSetting, KV_KEY)
    if not row or not row.value:
        return HubSettings()
    try:
        data = json.loads(row.value)
        return HubSettings.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return HubSettings()


def save_hub_settings(db: Session, s: HubSettings) -> None:
    row = db.get(KVSetting, KV_KEY)
    payload = s.model_dump(mode="json")
    text = json.dumps(payload)
    if row:
        row.value = text
    else:
        db.add(KVSetting(key=KV_KEY, value=text))
    db.commit()


def merge_hub_settings(db: Session, patch: dict[str, Any]) -> HubSettings:
    current = load_hub_settings(db)
    data = current.model_dump()
    allowed = set(HubSettings.model_fields.keys())
    for k, v in patch.items():
        if k in allowed:
            data[k] = v
    out = HubSettings.model_validate(data)
    save_hub_settings(db, out)
    return out
