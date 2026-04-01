"""Simple ECG filtering utilities."""

from __future__ import annotations

import numpy as np


class ECGFilter:
    """Lightweight moving-average high-pass approximation.

    Note:
        This is a provisional filter for scaffold stage.
    """

    def __init__(self, sampling_rate_hz: int) -> None:
        self._window = max(3, sampling_rate_hz // 5)
        self._buffer: list[float] = []

    def process(self, ecg_uv: float) -> float:
        """Process one sample and return filtered value."""
        self._buffer.append(ecg_uv)
        if len(self._buffer) > self._window:
            self._buffer.pop(0)
        baseline = float(np.mean(self._buffer))
        return ecg_uv - baseline
