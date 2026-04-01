"""Heart-rate computations and trend estimation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Heartbeat:
    """Derived heartbeat metrics."""

    beat_id: int
    timestamp_ns: int
    rr_interval_ms: float | None
    heart_rate_bpm: float | None


class HeartRateEstimator:
    """Converts peak timestamps to RR and instantaneous HR."""

    def __init__(self) -> None:
        self._last_peak_ns: int | None = None
        self._beat_id = 0
        self._history: list[tuple[int, float]] = []

    def on_peak(self, timestamp_ns: int) -> Heartbeat:
        """Handle peak timestamp and return derived heartbeat record."""
        self._beat_id += 1
        rr_ms: float | None = None
        hr_bpm: float | None = None
        if self._last_peak_ns is not None:
            rr_ms = (timestamp_ns - self._last_peak_ns) / 1_000_000.0
            if rr_ms > 0:
                hr_bpm = 60000.0 / rr_ms
                self._history.append((timestamp_ns, hr_bpm))
        self._last_peak_ns = timestamp_ns
        return Heartbeat(
            beat_id=self._beat_id,
            timestamp_ns=timestamp_ns,
            rr_interval_ms=rr_ms,
            heart_rate_bpm=hr_bpm,
        )

    def trend(self, now_ns: int, window_seconds: float, threshold_bpm: float) -> tuple[float | None, float | None, str]:
        """Compare recent and previous windows and return trend label."""
        window_ns = int(window_seconds * 1_000_000_000)
        current = [v for ts, v in self._history if now_ns - window_ns < ts <= now_ns]
        previous = [v for ts, v in self._history if now_ns - 2 * window_ns < ts <= now_ns - window_ns]
        if not current or not previous:
            return (None, None, "stable")
        avg_cur = sum(current) / len(current)
        avg_prev = sum(previous) / len(previous)
        delta = avg_cur - avg_prev
        if delta >= threshold_bpm:
            return (avg_cur, avg_prev, "increasing")
        if delta <= -threshold_bpm:
            return (avg_cur, avg_prev, "decreasing")
        return (avg_cur, avg_prev, "stable")
