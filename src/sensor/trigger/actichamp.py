"""ActiCHamp trigger implementation."""

from __future__ import annotations

import asyncio
import serial


class ActiChampTrigger:
    """Serial trigger sender for ActiCHamp."""

    name = "actichamp"

    def __init__(self, port: str, baudrate: int, enabled: bool = True) -> None:
        self._port = port
        self._baudrate = baudrate
        self._enabled = enabled
        self._connection: serial.Serial | None = None

    def connect(self) -> bool:
        """Connect serial device."""
        if not self._enabled:
            return True
        try:
            self._connection = serial.Serial(port=self._port, baudrate=self._baudrate)
            return True
        except serial.SerialException:
            return False

    async def send(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        """Send pulse without blocking the asyncio loop."""
        if not self._enabled:
            return True
        if self._connection is None or not self._connection.is_open:
            return False
        try:
            self._connection.write(bytes([trigger_value]))
            await asyncio.sleep(reset_pulse_seconds)
            self._connection.write(bytes([0]))
            return True
        except serial.SerialException:
            return False
