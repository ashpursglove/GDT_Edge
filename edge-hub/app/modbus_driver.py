"""
Modbus RTU device drivers (presets + custom reads).
Aligned with legacy `old control system/modules/modbus_devices.py`.
"""

from __future__ import annotations

import json
from typing import Any

import minimalmodbus
import serial

# --- Presets -----------------------------------------------------------------


class CwtBlPhSensor:
    REG_TEMPERATURE = 0
    REG_PH = 1

    def __init__(
        self,
        port: str | serial.Serial,
        slave_address: int = 1,
        baudrate: int = 9600,
        timeout: float = 0.5,
        debug: bool = False,
    ) -> None:
        instrument = minimalmodbus.Instrument(port, slave_address)  # type: ignore[arg-type]
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True
        if isinstance(port, str):
            instrument.serial.baudrate = baudrate
            instrument.serial.bytesize = 8
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout = timeout
        instrument.debug = debug
        self._instrument = instrument

    def read_all(self) -> tuple[float, float]:
        temp = self._instrument.read_register(
            registeraddress=self.REG_TEMPERATURE,
            number_of_decimals=1,
            functioncode=3,
            signed=True,
        )
        ph = self._instrument.read_register(
            registeraddress=self.REG_PH,
            number_of_decimals=1,
            functioncode=3,
            signed=False,
        )
        return float(temp), float(ph)


class As7341Controller:
    REG_LED_CONTROL = 0
    REG_RELAY_CONTROL = 1
    REG_FIRST_SPECTRAL = 2
    NUM_SPECTRAL_REGS = 10
    REG_STATUS_WORD = 12

    def __init__(
        self,
        port: str | serial.Serial,
        slave_address: int = 50,
        baudrate: int = 9600,
        timeout: float = 0.5,
        debug: bool = False,
    ) -> None:
        instrument = minimalmodbus.Instrument(port, slave_address)  # type: ignore[arg-type]
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True
        if isinstance(port, str):
            instrument.serial.baudrate = baudrate
            instrument.serial.bytesize = 8
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout = timeout
        instrument.debug = debug
        self._instrument = instrument

    def read_spectral(self) -> tuple[list[int], int]:
        raw_values = self._instrument.read_registers(
            registeraddress=self.REG_FIRST_SPECTRAL,
            number_of_registers=self.NUM_SPECTRAL_REGS,
            functioncode=3,
        )
        if len(raw_values) >= 10:
            values = raw_values[:8] + raw_values[9:]
        else:
            values = raw_values
        status_word = self._instrument.read_register(
            registeraddress=self.REG_STATUS_WORD,
            number_of_decimals=0,
            functioncode=3,
            signed=False,
        )
        return values, int(status_word)

    def write_led(self, value: int) -> None:
        self._instrument.write_register(
            registeraddress=self.REG_LED_CONTROL,
            value=1 if value != 0 else 0,
            number_of_decimals=0,
            functioncode=6,
            signed=False,
        )

    def write_relay(self, value: int) -> None:
        self._instrument.write_register(
            registeraddress=self.REG_RELAY_CONTROL,
            value=1 if value != 0 else 0,
            number_of_decimals=0,
            functioncode=6,
            signed=False,
        )


class CustomMapReader:
    """
    Reads registers from JSON config:
    {
      "registers": [
        {"address": 0, "function_code": 3, "count": 1, "decimals": 1, "signed": true, "name": "x"}
      ]
    }
    """

    def __init__(
        self,
        port: str | serial.Serial,
        slave_address: int,
        config_json: str,
        baudrate: int = 9600,
        timeout: float = 0.5,
    ) -> None:
        self._data = json.loads(config_json) if config_json else {"registers": []}
        self._slave = slave_address
        instrument = minimalmodbus.Instrument(port, slave_address)  # type: ignore[arg-type]
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.clear_buffers_before_each_transaction = True
        if isinstance(port, str):
            instrument.serial.baudrate = baudrate
            instrument.serial.bytesize = 8
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout = timeout
        self._instrument = instrument

    def read_values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for spec in self._data.get("registers", []):
            addr = int(spec["address"])
            fc = int(spec.get("function_code", 3))
            name = str(spec.get("name", f"reg_{addr}"))
            count = int(spec.get("count", 1))
            if count == 1 and fc in (3, 4):
                decimals = int(spec.get("decimals", 0))
                signed = bool(spec.get("signed", False))
                val = self._instrument.read_register(
                    registeraddress=addr,
                    number_of_decimals=decimals,
                    functioncode=fc,
                    signed=signed,
                )
                out[name] = float(val)
            elif fc in (3, 4) and count > 1:
                regs = self._instrument.read_registers(
                    registeraddress=addr,
                    number_of_registers=count,
                    functioncode=fc,
                )
                vals = [int(x) for x in regs]
                drop_indices = spec.get("drop_indices")
                if isinstance(drop_indices, list) and drop_indices:
                    drops = {int(i) for i in drop_indices if isinstance(i, (int, float, str))}
                    vals = [v for i, v in enumerate(vals) if i not in drops]
                take = spec.get("take")
                if isinstance(take, int) and take > 0:
                    vals = vals[:take]
                out[name] = vals
            else:
                out[name] = None
        return out


def build_preset(
    kind: str,
    port: serial.Serial,
    slave_id: int,
    baudrate: int,
    timeout: float,
) -> Any:
    if kind == "ph_temp":
        return CwtBlPhSensor(port, slave_address=slave_id, baudrate=baudrate, timeout=timeout)
    if kind == "spectral":
        return As7341Controller(port, slave_address=slave_id, baudrate=baudrate, timeout=timeout)
    raise ValueError(f"Unknown preset kind: {kind}")
