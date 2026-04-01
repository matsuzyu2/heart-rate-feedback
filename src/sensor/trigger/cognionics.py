"""Cognionics trigger implementation via ZMQ and optional serial."""

from __future__ import annotations

import asyncio
import zmq
import serial


class CognionicsTrigger:
    """Trigger sender for Cognionics over ZMQ and serial in parallel."""

    name = "cognionics"

    def __init__(
        self,
        zmq_address: str,
        serial_port: str,
        serial_baudrate: int,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._zmq_address = zmq_address
        self._serial_port = serial_port
        self._serial_baudrate = serial_baudrate
        self._ctx: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._serial: serial.Serial | None = None

    def connect(self) -> bool:
        """Connect available channels."""
        if not self._enabled:
            return True
        zmq_ok = False
        serial_ok = False
        try:
            self._ctx = zmq.Context()
            self._socket = self._ctx.socket(zmq.PUSH)
            self._socket.connect(self._zmq_address)
            zmq_ok = True
        except zmq.ZMQError:
            zmq_ok = False

        try:
            self._serial = serial.Serial(self._serial_port, self._serial_baudrate)
            serial_ok = True
        except serial.SerialException:
            serial_ok = False

        return zmq_ok or serial_ok

    async def send(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        """Send trigger via both channels concurrently when available."""
        if not self._enabled:
            return True

        tasks: list[asyncio.Task[bool]] = []
        if self._socket is not None:
            tasks.append(asyncio.create_task(self._send_zmq(trigger_value, reset_pulse_seconds)))
        if self._serial is not None and self._serial.is_open:
            tasks.append(asyncio.create_task(self._send_serial(trigger_value, reset_pulse_seconds)))
        if not tasks:
            return False
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return any(isinstance(value, bool) and value for value in results)

    async def _send_zmq(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        if self._socket is None:
            return False
        try:
            self._socket.send_string(str(trigger_value), flags=zmq.NOBLOCK)
            await asyncio.sleep(reset_pulse_seconds)
            self._socket.send_string("0", flags=zmq.NOBLOCK)
            return True
        except zmq.ZMQError:
            return False

    async def _send_serial(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        if self._serial is None:
            return False
        try:
            self._serial.write(bytes([trigger_value]))
            await asyncio.sleep(reset_pulse_seconds)
            self._serial.write(bytes([0]))
            return True
        except serial.SerialException:
            return False
