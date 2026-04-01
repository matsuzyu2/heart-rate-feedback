"""Polar H10 ECG BLE streaming client."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

logger = logging.getLogger(__name__)

# Polar PMD (Polar Measurement Data) service / characteristic UUIDs
ECG_SERVICE_UUID = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
ECG_CONTROL_POINT_UUID = "fb005c81-02e7-f387-1cad-8acd2d8df0c8"
ECG_DATA_UUID = "fb005c82-02e7-f387-1cad-8acd2d8df0c8"

# Commands
_START_COMMAND = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
_STOP_COMMAND = bytearray([0x03, 0x00])

# Timing constants
_SCAN_TIMEOUT_SECONDS = 10.0
_TRANSITION_PERIOD_SECONDS = 10.0
_SAMPLE_INTERVAL_NS = 1_000_000_000 // 130  # ~7_692_307 ns per sample at 130 Hz

SampleCallback = Callable[[int, int], Awaitable[None] | None]
"""Callback type: (timestamp_ns: int, ecg_uv: int) -> None."""


class PolarECGClient:
    """BLE client for Polar H10 ECG streaming.

    Connects to a Polar H10 device by scanning for a device whose name
    contains both "Polar" and the given ``device_id`` string.  After
    calling :meth:`start_streaming`, each ECG sample is forwarded to the
    provided :data:`SampleCallback` as ``(timestamp_ns, ecg_uv)``.

    Transition period:
        The first 10 seconds of samples are discarded to allow the filter
        capacitors to settle.  The :attr:`clock_sync` property is set from
        the very first sample that arrives (before transition filtering).

    Args:
        device_id: Partial device name / serial suffix used to identify the
            target Polar device (e.g. ``"D1948025"``).
        sampling_rate_hz: ECG sampling rate reported by the device.
            Defaults to 130 Hz.
    """

    def __init__(self, device_id: str, sampling_rate_hz: int = 130) -> None:
        self.device_id = device_id
        self.sampling_rate_hz = sampling_rate_hz

        self._device: Optional[BLEDevice] = None
        self._client: Optional[BleakClient] = None
        self._is_connected: bool = False
        self._is_streaming: bool = False

        # Per-stream state (reset on each start_streaming call)
        self._callback: Optional[SampleCallback] = None
        self._streaming_start_ns: Optional[int] = None
        self._transition_passed: bool = False
        self._first_sample_received: bool = False

        # Clock synchronisation (set on very first sample)
        self._clock_sync: Optional[dict[str, int | str]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def clock_sync(self) -> dict[str, int | str] | None:
        """Clock sync dict after first sample received, else ``None``.

        Keys:
            polar_first_timestamp_ns: Polar device timestamp of first sample.
            system_time_ns_at_first_sample: ``time.time_ns()`` recorded when
                the first BLE notification arrived.
            note: Human-readable description.
        """
        return self._clock_sync

    async def connect(self) -> bool:
        """Scan for and connect to the target Polar H10 device.

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        try:
            self._device = await self._find_polar_device()
            if self._device is None:
                logger.error("Polar device with ID '%s' not found during scan", self.device_id)
                return False

            logger.info("Connecting to %s (%s)", self._device.name, self._device.address)
            self._client = BleakClient(
                self._device,
                disconnected_callback=self._on_disconnected,
            )
            await self._client.connect()
            self._is_connected = True
            logger.info("Connected to Polar H10 successfully")
            return True

        except Exception:
            logger.exception("Failed to connect to Polar H10")
            return False

    async def disconnect(self) -> None:
        """Stop streaming (if active) and disconnect BLE."""
        if self._is_streaming:
            await self.stop_streaming()

        if self._client and self._is_connected:
            try:
                await self._client.disconnect()
                logger.info("Disconnected from Polar H10")
            except Exception:
                logger.exception("Error during BLE disconnect")
            finally:
                self._is_connected = False

    async def start_streaming(self, callback: SampleCallback) -> bool:
        """Start ECG streaming and register sample callback.

        Args:
            callback: Called for each ECG sample after the transition period.
                Signature: ``(timestamp_ns: int, ecg_uv: int) -> None``.

        Returns:
            ``True`` if streaming started successfully, ``False`` otherwise.
        """
        if not self._is_connected or self._client is None:
            logger.error("Cannot start streaming: not connected")
            return False

        self._callback = callback
        self._streaming_start_ns = None
        self._transition_passed = False
        self._first_sample_received = False
        self._is_streaming = True

        try:
            await self._client.start_notify(ECG_DATA_UUID, self._on_ecg_notification)
            # Give the device time to register the notification subscription
            import asyncio
            await asyncio.sleep(2.0)

            await self._client.write_gatt_char(ECG_CONTROL_POINT_UUID, _START_COMMAND)
            await asyncio.sleep(2.0)

            if not self._client.is_connected:
                logger.error("BLE session closed after sending start command")
                self._is_streaming = False
                return False

            logger.info("ECG streaming started")
            return True

        except Exception:
            logger.exception("Failed to start ECG streaming")
            self._is_streaming = False
            return False

    async def stop_streaming(self) -> None:
        """Send stop command and unregister BLE notifications."""
        if not self._is_streaming:
            return

        try:
            if self._client and self._client.is_connected:
                await self._client.write_gatt_char(ECG_CONTROL_POINT_UUID, _STOP_COMMAND)
                await self._client.stop_notify(ECG_DATA_UUID)
                logger.info("ECG streaming stopped")
            else:
                logger.warning("Client not connected — cannot send stop command")
        except Exception:
            logger.exception("Error stopping ECG streaming")
        finally:
            self._is_streaming = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_polar_device(self) -> Optional[BLEDevice]:
        """Scan for BLE devices and return the matching Polar device."""
        logger.info("Scanning for Polar device with ID '%s'…", self.device_id)
        devices = await BleakScanner.discover(timeout=_SCAN_TIMEOUT_SECONDS)
        for device in devices:
            if device.name and "Polar" in device.name and self.device_id in device.name:
                logger.info("Found Polar device: %s (%s)", device.name, device.address)
                return device
        return None

    def _on_disconnected(self, client: BleakClient) -> None:
        """BLE disconnection callback."""
        logger.warning("BLE disconnection detected")
        self._is_connected = False
        self._is_streaming = False

    async def _on_ecg_notification(self, sender: int, data: bytearray) -> None:
        """Handle incoming BLE notification from ECG_DATA_UUID."""
        try:
            samples = self._parse_ecg_packet(data)
        except ValueError as exc:
            logger.warning("ECG parse error: %s", exc)
            return

        for timestamp_ns, ecg_uv in samples:
            # Record clock sync on the very first sample ever received
            if not self._first_sample_received:
                self._first_sample_received = True
                system_ns = time.time_ns()
                self._clock_sync = {
                    "polar_first_timestamp_ns": timestamp_ns,
                    "system_time_ns_at_first_sample": system_ns,
                    "note": "Polar device timestamp paired with host time.time_ns()",
                }
                self._streaming_start_ns = timestamp_ns
                logger.info(
                    "Clock sync recorded: polar_ts=%d system_ns=%d",
                    timestamp_ns,
                    system_ns,
                )

            # Skip transition period samples
            if not self._transition_passed:
                assert self._streaming_start_ns is not None
                elapsed = (timestamp_ns - self._streaming_start_ns) / 1_000_000_000
                if elapsed < _TRANSITION_PERIOD_SECONDS:
                    continue
                self._transition_passed = True
                logger.info("Transition period ended — forwarding ECG samples")

            if self._callback is not None:
                result = self._callback(timestamp_ns, ecg_uv)
                if result is not None:
                    import inspect
                    if inspect.isawaitable(result):
                        await result

    @staticmethod
    def _parse_ecg_packet(data: bytearray) -> list[tuple[int, int]]:
        """Parse a raw Polar PMD ECG BLE notification packet.

        Packet layout:
            Byte  0    : data type (must be 0x00 = ECG)
            Bytes 1-8  : Polar timestamp (uint64 LE, nanoseconds)
            Byte  9    : frame type (must be 0x00)
            Bytes 10+  : ECG samples, 3 bytes each (signed int24 LE)

        Args:
            data: Raw BLE notification payload.

        Returns:
            List of ``(timestamp_ns, ecg_uv)`` tuples, one per sample.

        Raises:
            ValueError: If the packet is malformed or uses an unsupported type.
        """
        if len(data) < 10:
            raise ValueError(f"Packet too short: {len(data)} bytes")

        if data[0] != 0x00:
            raise ValueError(f"Unexpected data type byte: 0x{data[0]:02X}")

        timestamp_ns = int.from_bytes(data[1:9], byteorder="little", signed=False)
        frame_type = data[9]

        if frame_type != 0x00:
            raise ValueError(f"Unsupported frame type: 0x{frame_type:02X}")

        payload = data[10:]
        bytes_per_sample = 3
        sample_count = len(payload) // bytes_per_sample

        results: list[tuple[int, int]] = []
        sample_interval_ns = 1_000_000_000 // 130

        for i in range(sample_count):
            offset = i * bytes_per_sample
            ecg_uv = int.from_bytes(
                payload[offset : offset + bytes_per_sample],
                byteorder="little",
                signed=True,
            )
            sample_ts = timestamp_ns + i * sample_interval_ns
            results.append((sample_ts, ecg_uv))

        return results
