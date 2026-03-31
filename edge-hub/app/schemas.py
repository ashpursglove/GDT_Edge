from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HubSettings(BaseModel):
    api_base_url: str = ""
    api_key: str = ""
    serial_port: str = ""
    baud_rate: int = 9600
    poll_interval_ms: int = 1000
    sync_interval_sec: int = 60
    selected_site_id: int | None = None
    last_upload_success_utc: datetime | None = None
    last_upload_detail: str = ""


class LocalReactorPatch(BaseModel):
    """Binding comes from the console; only runtime flag is editable."""

    enabled: bool = True


class LocalReactorOut(BaseModel):
    id: int
    label: str
    site_id: int | None
    server_reactor_id: int | None
    enabled: bool

    model_config = {"from_attributes": True}


class DeviceCreate(BaseModel):
    kind: str = Field(..., description="Sensor array code from console DB (e.g. ph-temp, spectral-as7341)")
    name: str = ""
    slave_id: int = Field(..., ge=1, le=247)
    custom_config_json: str | None = None


class DeviceOut(BaseModel):
    id: int
    reactor_id: int
    kind: str
    name: str
    slave_id: int
    custom_config_json: str | None

    model_config = {"from_attributes": True}


class LocalReactorWithDevicesOut(LocalReactorOut):
    """List view including Modbus devices for at-a-glance display in the UI."""

    devices: list[DeviceOut] = []


class SiteDTO(BaseModel):
    id: int
    slug: str | None = None
    name: str | None = None


class ReactorDTO(BaseModel):
    id: int
    name: str
    site_id: int | None = None


class SensorDTO(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    kind: str
    outputs: Any | None = None
    notes: str | None = None


class ControlStatus(BaseModel):
    running: bool
    last_error: str | None = None
    last_poll_utc: datetime | None = None
    serial_open: bool = False
    pending_uploads: int = 0
    last_upload_success_utc: datetime | None = None
    last_upload_detail: str = ""


class LiveSnapshot(BaseModel):
    reactor_id: int
    label: str
    server_reactor_id: int | None
    reading_at: datetime | None = None
    temperature_c: float | None = None
    ph: float | None = None
    spectral: list[int] | None = None
    spectral_status: int | None = None
    custom: dict[str, Any] | None = None
    error: str | None = None


class IngestReading(BaseModel):
    reactor_id: int
    reading_at: datetime
    temperature_c: float | None = None
    ph: float | None = None
    ph_raw: float | None = None
    spectral: list[int] | None = None
    spectral_status: int | None = None
