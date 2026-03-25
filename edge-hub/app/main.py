from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db, init_db
from app.models import Device, LocalReactor
from app.remote_client import RemoteAPIError, fetch_reactors, fetch_sites, fetch_sensors
from app.schemas import (
    DeviceCreate,
    DeviceOut,
    HubSettings,
    LocalReactorOut,
    LocalReactorPatch,
)
from app.services.runtime import runtime
from app.services.settings_store import load_hub_settings, merge_hub_settings, save_hub_settings
from app.services.sensors_store import load_sensors, save_sensors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    runtime.stop()


app = FastAPI(title="GDT Edge Hub", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings", response_model=HubSettings)
def get_settings(db: Session = Depends(get_db)) -> HubSettings:
    return load_hub_settings(db)


@app.put("/api/settings", response_model=HubSettings)
def put_settings(body: HubSettings, db: Session = Depends(get_db)) -> HubSettings:
    save_hub_settings(db, body)
    return load_hub_settings(db)


@app.patch("/api/settings", response_model=HubSettings)
def patch_settings(patch: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> HubSettings:
    return merge_hub_settings(db, patch)


@app.get("/api/serial-ports")
def serial_ports() -> dict[str, list[str]]:
    try:
        from serial.tools import list_ports

        ports = [p.device for p in list_ports.comports()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("serial port enumeration failed: %s", exc)
        ports = []
    return {"ports": ports}


@app.get("/api/remote/sites")
def api_remote_sites(db: Session = Depends(get_db)) -> dict:
    s = load_hub_settings(db)
    if not s.api_base_url.strip() or not s.api_key.strip():
        raise HTTPException(400, "Configure API base URL and API key first")
    try:
        sites = fetch_sites(s.api_base_url, s.api_key)
        return {"sites": [x.model_dump() for x in sites]}
    except RemoteAPIError as exc:
        raise HTTPException(exc.status_code or 502, str(exc)) from exc


@app.get("/api/remote/sites/{site_id}/reactors")
def api_remote_reactors(site_id: int, db: Session = Depends(get_db)) -> dict:
    s = load_hub_settings(db)
    if not s.api_base_url.strip() or not s.api_key.strip():
        raise HTTPException(400, "Configure API base URL and API key first")
    try:
        reactors = fetch_reactors(s.api_base_url, s.api_key, site_id)
        return {"reactors": [x.model_dump() for x in reactors]}
    except RemoteAPIError as exc:
        raise HTTPException(exc.status_code or 502, str(exc)) from exc


@app.get("/api/remote/sensors")
def api_remote_sensors(db: Session = Depends(get_db)) -> dict:
    s = load_hub_settings(db)
    if not s.api_base_url.strip() or not s.api_key.strip():
        raise HTTPException(400, "Configure API base URL and API key first")
    try:
        sensors = fetch_sensors(s.api_base_url, s.api_key)
        return {"sensors": [x.model_dump() for x in sensors]}
    except RemoteAPIError as exc:
        raise HTTPException(exc.status_code or 502, str(exc)) from exc


@app.post("/api/remote/sensors/sync")
def sync_sensors(db: Session = Depends(get_db)) -> dict:
    s = load_hub_settings(db)
    if not s.api_base_url.strip() or not s.api_key.strip():
        raise HTTPException(400, "Configure API base URL and API key first")
    try:
        sensors = fetch_sensors(s.api_base_url, s.api_key)
        save_sensors(db, [x.model_dump() for x in sensors])
        return {"ok": True, "count": len(sensors)}
    except RemoteAPIError as exc:
        raise HTTPException(exc.status_code or 502, str(exc)) from exc


def _effective_site_id(db: Session, site_id: int | None) -> int | None:
    if site_id is not None:
        return site_id
    return load_hub_settings(db).selected_site_id


@app.get("/api/local-reactors", response_model=list[LocalReactorOut])
def list_local_reactors(
    site_id: int | None = Query(None, description="Filter to console site; defaults to saved selection"),
    db: Session = Depends(get_db),
) -> list[LocalReactor]:
    sid = _effective_site_id(db, site_id)
    if sid is None:
        return []
    return list(
        db.execute(
            select(LocalReactor)
            .where(LocalReactor.site_id == sid)
            .order_by(LocalReactor.id)
        )
        .scalars()
        .all()
    )


@app.post("/api/local-reactors/sync")
def sync_local_reactors_from_console(
    site_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict[str, int | list[dict[str, int | str]]]:
    """
    Fetch reactors for this site from the console and mirror them locally.
    Creates/updates rows; removes local rows (and devices) for reactors no longer on the console.
    """
    if site_id < 1:
        raise HTTPException(400, "Invalid site_id")

    hub = load_hub_settings(db)
    if not hub.api_base_url.strip() or not hub.api_key.strip():
        raise HTTPException(400, "Configure API base URL and API key first")

    try:
        remote = fetch_reactors(hub.api_base_url, hub.api_key, site_id)
    except RemoteAPIError as exc:
        raise HTTPException(exc.status_code or 502, str(exc)) from exc

    try:
        remote_ids = {r.id for r in remote}

        existing_rows = (
            db.execute(
                select(LocalReactor)
                .options(joinedload(LocalReactor.devices))
                .where(LocalReactor.site_id == site_id)
            )
            .scalars()
            .unique()
            .all()
        )
        by_server_id: dict[int, LocalReactor] = {}
        for row in existing_rows:
            if row.server_reactor_id is not None:
                by_server_id[row.server_reactor_id] = row

        for srv_id, row in list(by_server_id.items()):
            if srv_id not in remote_ids:
                db.delete(row)

        for r in remote:
            row = by_server_id.get(r.id)
            if row is not None:
                row.label = r.name
            else:
                db.add(
                    LocalReactor(
                        label=r.name,
                        site_id=site_id,
                        server_reactor_id=r.id,
                        enabled=True,
                    )
                )

        save_hub_settings(
            db,
            HubSettings(
                api_base_url=hub.api_base_url,
                api_key=hub.api_key,
                serial_port=hub.serial_port,
                baud_rate=hub.baud_rate,
                poll_interval_ms=hub.poll_interval_ms,
                sync_interval_sec=hub.sync_interval_sec,
                selected_site_id=site_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync_local_reactors_from_console failed")
        db.rollback()
        raise HTTPException(500, f"Sync failed: {exc}") from exc

    return {
        "site_id": site_id,
        "reactors": [{"id": r.id, "name": r.name} for r in remote],
    }


@app.patch("/api/local-reactors/{reactor_id}", response_model=LocalReactorOut)
def update_local_reactor(
    reactor_id: int,
    body: LocalReactorPatch,
    db: Session = Depends(get_db),
) -> LocalReactor:
    r = db.get(LocalReactor, reactor_id)
    if not r:
        raise HTTPException(404, "Reactor not found")
    r.enabled = body.enabled
    db.commit()
    db.refresh(r)
    return r


@app.get("/api/local-reactors/{reactor_id}/devices", response_model=list[DeviceOut])
def list_devices(reactor_id: int, db: Session = Depends(get_db)) -> list[Device]:
    r = db.get(LocalReactor, reactor_id)
    if not r:
        raise HTTPException(404, "Reactor not found")
    return list(db.execute(select(Device).where(Device.reactor_id == reactor_id).order_by(Device.id)).scalars().all())


@app.post("/api/local-reactors/{reactor_id}/devices", response_model=DeviceOut)
def add_device(reactor_id: int, body: DeviceCreate, db: Session = Depends(get_db)) -> Device:
    r = db.get(LocalReactor, reactor_id)
    if not r:
        raise HTTPException(404, "Reactor not found")
    if body.kind == "custom":
        raise HTTPException(400, "custom devices are disabled; choose a Sensor Array from the console DB")
    known = {s.get("code") for s in load_sensors(db) if isinstance(s, dict)}
    if body.kind not in known:
        raise HTTPException(400, "Unknown sensor code. Sync sensors from console first.")
    d = Device(
        reactor_id=reactor_id,
        kind=body.kind,
        name=body.name or body.kind,
        slave_id=body.slave_id,
        custom_config_json=body.custom_config_json,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@app.patch("/api/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, body: DeviceCreate, db: Session = Depends(get_db)) -> Device:
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")
    if body.kind == "custom":
        raise HTTPException(400, "custom devices are disabled; choose a Sensor Array from the console DB")
    known = {s.get("code") for s in load_sensors(db) if isinstance(s, dict)}
    if body.kind not in known:
        raise HTTPException(400, "Unknown sensor code. Sync sensors from console first.")
    d.kind = body.kind
    d.name = body.name or body.kind
    d.slave_id = body.slave_id
    d.custom_config_json = body.custom_config_json
    db.commit()
    db.refresh(d)
    return d


@app.delete("/api/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")
    db.delete(d)
    db.commit()
    return {"ok": True}


@app.post("/api/control/start")
def control_start() -> dict[str, bool]:
    runtime.start()
    return {"ok": True}


@app.post("/api/control/stop")
def control_stop() -> dict[str, bool]:
    runtime.stop()
    return {"ok": True}


@app.get("/api/status")
def api_status() -> dict:
    st = runtime.status_dict()
    return st


@app.get("/api/live")
def api_live() -> dict:
    return {
        "snapshots": [s.model_dump() for s in runtime.live_snapshots()],
        "status": runtime.status_dict(),
    }


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(500, "static UI missing")
    return FileResponse(index_path)
