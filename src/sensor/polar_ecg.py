"""Polar ECG interface scaffold for BLE streaming."""

from __future__ import annotations

from collections.abc import Awaitable, Callable


SampleCallback = Callable[[int, int], Awaitable[None] | None]


class PolarECGClient:
    """Placeholder client for Polar H10 ECG streaming.

    The full BLE implementation is connected in a later phase.
    """

    def __init__(self, device_id: str, sampling_rate_hz: int) -> None:
        self.device_id = device_id
        self.sampling_rate_hz = sampling_rate_hz
        self._running = False

    async def start_streaming(self, callback: SampleCallback) -> None:
        """Start ECG stream and push samples to callback."""
        self._running = True
        _ = callback

    async def stop_streaming(self) -> None:
        """Stop ECG streaming."""
        self._running = False
