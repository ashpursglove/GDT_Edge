from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KVSetting(Base):
    __tablename__ = "kv_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class LocalReactor(Base):
    """A logical reactor on the RS485 bus, bound to a server reactor row."""

    __tablename__ = "local_reactors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(256), default="Reactor")
    site_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    server_reactor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    devices: Mapped[list["Device"]] = relationship(
        "Device",
        back_populates="reactor",
        cascade="all, delete-orphan",
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reactor_id: Mapped[int] = mapped_column(Integer, ForeignKey("local_reactors.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # ph_temp, spectral, custom
    name: Mapped[str] = mapped_column(String(256), default="")
    slave_id: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    reactor: Mapped["LocalReactor"] = relationship("LocalReactor", back_populates="devices")


class ReadingOutbox(Base):
    """Queued telemetry for POST to the console ingest API."""

    __tablename__ = "reading_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reactor_id: Mapped[int] = mapped_column(Integer, ForeignKey("local_reactors.id"), nullable=False)
    reading_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
