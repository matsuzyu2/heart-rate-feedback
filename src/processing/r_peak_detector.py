"""Streaming R-peak detector using derivative heuristics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeakEvent:
    """Detected R-peak event."""

    timestamp_ns: int
    amplitude_uv: float


class RPeakDetector:
    """Simple detector with refractory period."""

    def __init__(self, refractory_period_ms: int, sampling_rate_hz: int) -> None:
        self._refractory_samples = int((refractory_period_ms / 1000.0) * sampling_rate_hz)
        self._last_peak_index = -10**9
        self._index = 0
        self._prev = 0.0
        self._prev_diff = 0.0

    def update(self, timestamp_ns: int, value: float) -> PeakEvent | None:
        """Return PeakEvent if an R-peak is detected."""
        diff = value - self._prev
        is_zero_cross = self._prev_diff > 0 and diff <= 0
        ready = (self._index - self._last_peak_index) >= self._refractory_samples
        if is_zero_cross and ready and self._prev > 40.0:
            self._last_peak_index = self._index
            event = PeakEvent(timestamp_ns=timestamp_ns, amplitude_uv=self._prev)
        else:
            event = None

        self._prev_diff = diff
        self._prev = value
        self._index += 1
        return event
