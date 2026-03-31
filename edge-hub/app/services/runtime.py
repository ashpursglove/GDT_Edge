from __future__ import annotations

import json
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import serial
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.modbus_driver import CustomMapReader
from app.models import LocalReactor, ReadingOutbox
from app.remote_client import post_readings, RemoteAPIError
from app.services.settings_store import load_hub_settings, save_hub_settings
from app.services.sensors_store import load_sensors
from app.schemas import LiveSnapshot

logger = logging.getLogger(__name__)

# Larger batches drain backlogs faster; console accepts batched readings.
_OUTBOX_BATCH = 80
# Short pause between batches when a backlog exists (normal interval used when idle).
_DRAIN_PAUSE_SEC = 0.35


def _json_safe_float(x: float | None) -> float | None:
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


class HubRuntime:
    """
    Owns Modbus poll loop and outbound sync loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None
        self._running = False
        self._last_error: str | None = None
        self._last_poll_utc: datetime | None = None
        self._serial_open = False
        self._live: dict[int, LiveSnapshot] = {}
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, cb: Callable[[], None]) -> None:
        self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:  # noqa: BLE001
                logger.exception("listener failed")

    @property
    def running(self) -> bool:
        return self._running

    def status_dict(self) -> dict[str, Any]:
        with self._lock:
            pending = 0
            last_up: datetime | None = None
            last_detail = ""
            db = SessionLocal()
            try:
                pending = db.scalar(
                    select(func.count())
                    .select_from(ReadingOutbox)
                    .where(ReadingOutbox.sent_at.is_(None))
                ) or 0
                hub = load_hub_settings(db)
                last_up = hub.last_upload_success_utc
                last_detail = hub.last_upload_detail or ""
            finally:
                db.close()
            return {
                "running": self._running,
                "last_error": self._last_error,
                "last_poll_utc": self._last_poll_utc,
                "serial_open": self._serial_open,
                "pending_uploads": pending,
                "last_upload_success_utc": last_up,
                "last_upload_detail": last_detail,
            }

    def live_snapshots(self) -> list[LiveSnapshot]:
        with self._lock:
            return list(self._live.values())

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._stop.clear()
            self._running = True
            self._last_error = None
            self._poll_thread = threading.Thread(target=self._poll_loop, name="modbus-poll", daemon=True)
            self._sync_thread = threading.Thread(target=self._sync_loop, name="hub-sync", daemon=True)
            self._poll_thread.start()
            self._sync_thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._stop.set()
            self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
        if self._sync_thread:
            self._sync_thread.join(timeout=5.0)
        self._poll_thread = None
        self._sync_thread = None
        self._serial_open = False

    def _poll_loop(self) -> None:
        ser: serial.Serial | None = None
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                settings = load_hub_settings(db)
                port = settings.serial_port.strip()
                baud = settings.baud_rate
                interval_ms = max(200, settings.poll_interval_ms)

                if not port:
                    self._last_error = "Serial port not configured"
                    time.sleep(1.0)
                    continue

                if ser is None or not ser.is_open:
                    try:
                        ser = serial.Serial(
                            port=port,
                            baudrate=baud,
                            bytesize=8,
                            parity=serial.PARITY_NONE,
                            stopbits=1,
                            timeout=0.5,
                        )
                        self._serial_open = True
                    except serial.SerialException as exc:
                        self._last_error = f"Cannot open {port}: {exc}"
                        self._serial_open = False
                        time.sleep(2.0)
                        continue

                if settings.selected_site_id is None:
                    rows = []
                else:
                    rows = (
                        db.execute(
                            select(LocalReactor)
                            .options(joinedload(LocalReactor.devices))
                            .where(
                                and_(
                                    LocalReactor.enabled.is_(True),
                                    LocalReactor.site_id == settings.selected_site_id,
                                )
                            )
                            .order_by(LocalReactor.id)
                        )
                        .scalars()
                        .unique()
                        .all()
                    )

                now = datetime.now(timezone.utc)
                self._last_poll_utc = now

                for reactor in rows:
                    snap = self._read_one_reactor(ser, settings, reactor, now, db)
                    with self._lock:
                        self._live[reactor.id] = snap
                    self._notify()

            except Exception as exc:  # noqa: BLE001
                logger.exception("poll loop error")
                self._last_error = str(exc)
                db.rollback()
            finally:
                db.close()

            if self._stop.wait(timeout=interval_ms / 1000.0):
                break

        if ser and ser.is_open:
            ser.close()
        self._serial_open = False

    def _read_one_reactor(
        self,
        ser: serial.Serial,
        settings: Any,
        reactor: LocalReactor,
        now: datetime,
        db: Session,
    ) -> LiveSnapshot:
        temp_c: float | None = None
        ph: float | None = None
        spectral: list[int] | None = None
        spectral_status: int | None = None
        custom: dict[str, Any] = {}
        errors: list[str] = []

        baud = settings.baud_rate
        timeout = 0.5

        devices = sorted(reactor.devices, key=lambda d: d.id)
        sensors = load_sensors(db)
        sensor_by_code: dict[str, dict[str, Any]] = {
            s.get("code"): s for s in sensors if isinstance(s, dict) and isinstance(s.get("code"), str)
        }
        per_device_payloads: list[dict[str, Any]] = []
        for dev in devices:
            try:
                sensor = sensor_by_code.get(dev.kind)
                if not sensor:
                    errors.append(f"{dev.name or dev.kind}: unknown sensor code {dev.kind} (sync sensors)")
                    continue
                outputs = sensor.get("outputs") or {}
                modbus = outputs.get("modbus") if isinstance(outputs, dict) else None
                cfg = {"registers": modbus.get("registers", [])} if isinstance(modbus, dict) else {"registers": []}
                rdr = CustomMapReader(ser, dev.slave_id, json.dumps(cfg), baudrate=baud, timeout=timeout)
                vals = rdr.read_values()
                # Upload raw decoded values keyed by sensor code so the console can store/graph any sensor.
                if reactor.server_reactor_id and isinstance(vals, dict) and vals:
                    per_device_payloads.append(
                        {
                            "reactor_id": reactor.server_reactor_id,
                            "reading_at": now.isoformat(),
                            "sensor_code": dev.kind,
                            "values": vals,
                        }
                    )
                if sensor.get("kind") == "ph_temp":
                    if "temperature_c" in vals and vals["temperature_c"] is not None:
                        temp_c = float(vals["temperature_c"])
                    if "ph" in vals and vals["ph"] is not None:
                        ph = float(vals["ph"])
                elif sensor.get("kind") == "spectral":
                    sv = vals.get("spectral")
                    if isinstance(sv, list):
                        spectral = [int(x) for x in sv]
                    st = vals.get("spectral_status")
                    if st is not None:
                        spectral_status = int(st)
                else:
                    custom.update(vals)
            except Exception as exc:  # noqa: BLE001
                label = dev.name or dev.kind
                errors.append(f"{label}: {exc}")

        err_msg = "; ".join(errors) if errors else None

        snap = LiveSnapshot(
            reactor_id=reactor.id,
            label=reactor.label,
            server_reactor_id=reactor.server_reactor_id,
            reading_at=now,
            temperature_c=temp_c,
            ph=ph,
            spectral=spectral,
            spectral_status=spectral_status,
            custom=custom if custom else None,
            error=err_msg,
        )

        # Legacy combined payload (ph/temp/spectral only). Generic sensors are uploaded as per-device packets
        # with `sensor_code` + `values` (see `per_device_payloads` above).
        has_legacy_telemetry = (
            temp_c is not None
            or ph is not None
            or spectral is not None
            or spectral_status is not None
        )
        if reactor.server_reactor_id and has_legacy_telemetry:
            payload = {
                "reactor_id": reactor.server_reactor_id,
                "reading_at": now.isoformat(),
                "temperature_c": _json_safe_float(temp_c),
                "ph": _json_safe_float(ph),
                "ph_raw": _json_safe_float(ph),
                "spectral": spectral,
                "spectral_status": spectral_status,
            }
            try:
                payload_json = json.dumps(payload, allow_nan=False)
            except ValueError:
                logger.warning("skip outbox row: non-finite floats in payload for reactor %s", reactor.id)
            else:
                db.add(
                    ReadingOutbox(
                        reactor_id=reactor.id,
                        reading_at=now,
                        payload_json=payload_json,
                    )
                )
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

        # Also queue per-device payloads (sensor_code + values) for generic storage/graphing on the console.
        for p in per_device_payloads:
            try:
                payload_json = json.dumps(p, allow_nan=False)
            except ValueError:
                continue
            db.add(
                ReadingOutbox(
                    reactor_id=reactor.id,
                    reading_at=now,
                    payload_json=payload_json,
                )
            )
        if per_device_payloads:
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise

        return snap

    def _sync_loop(self) -> None:
        while not self._stop.is_set():
            db = SessionLocal()
            wait_sec = 60.0
            try:
                settings = load_hub_settings(db)
                interval = float(max(5, settings.sync_interval_sec))
                wait_sec = interval
                base = settings.api_base_url.strip()
                key = settings.api_key.strip()

                if base and key:
                    while not self._stop.is_set():
                        rows = (
                            db.execute(
                                select(ReadingOutbox)
                                .where(ReadingOutbox.sent_at.is_(None))
                                .order_by(ReadingOutbox.id)
                                .limit(_OUTBOX_BATCH)
                            )
                            .scalars()
                            .all()
                        )
                        if not rows:
                            break

                        readings: list[dict] = []
                        posted_rows: list[ReadingOutbox] = []
                        json_errors = False
                        for row in rows:
                            try:
                                readings.append(json.loads(row.payload_json))
                                posted_rows.append(row)
                            except json.JSONDecodeError:
                                row.last_error = "bad json"
                                row.attempts = row.attempts + 1
                                json_errors = True
                        if json_errors:
                            db.commit()
                        if not readings:
                            break

                        try:
                            post_readings(base, key, readings)
                            now = datetime.now(timezone.utc)
                            for row in posted_rows:
                                row.sent_at = now
                                row.last_error = None
                            hub = load_hub_settings(db)
                            hub.last_upload_success_utc = now
                            hub.last_upload_detail = (
                                f"Uploaded {len(readings)} reading(s) to GDT Console"
                            )
                            save_hub_settings(db, hub)
                            self._last_error = None
                        except RemoteAPIError as exc:
                            msg = str(exc)
                            if "Reactor not found:" in msg:
                                now = datetime.now(timezone.utc)
                                for row in posted_rows:
                                    row.sent_at = now
                                    row.last_error = msg[:2000]
                                    row.attempts = row.attempts + 1
                                db.commit()
                                self._last_error = (
                                    f"{msg} — resync reactors from console (Sites & reactors → select site) "
                                    "so local reactors point at valid console reactor ids."
                                )
                            else:
                                for row in posted_rows:
                                    row.last_error = msg[:2000]
                                    row.attempts = row.attempts + 1
                                db.commit()
                                self._last_error = msg
                            wait_sec = interval
                            break

                        remaining = (
                            db.scalar(
                                select(func.count())
                                .select_from(ReadingOutbox)
                                .where(ReadingOutbox.sent_at.is_(None))
                            )
                            or 0
                        )
                        if remaining > 0:
                            wait_sec = _DRAIN_PAUSE_SEC
                            if self._stop.wait(_DRAIN_PAUSE_SEC):
                                return
                            continue
                        wait_sec = interval
                        break
            except Exception as exc:  # noqa: BLE001
                logger.exception("sync loop")
                self._last_error = str(exc)
            finally:
                db.close()

            if self._stop.wait(timeout=wait_sec):
                break


runtime = HubRuntime()
