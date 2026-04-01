"""Online IIR bandpass ECG filter using cascaded biquad sections.

Implements a 2nd-order high-pass (at ``low_hz``) cascaded with a 2nd-order
low-pass (at ``high_hz``), both derived via the bilinear transform of a
Butterworth analogue prototype.  No external DSP libraries are required.

Bilinear-transform formulas used
---------------------------------
Let ``wc = tan(pi * fc / fs)`` and ``k = 1 / (1 + sqrt(2)*wc + wc^2)``.

2nd-order low-pass Butterworth
    b = [k*wc^2,  2*k*wc^2,  k*wc^2]
    a = [1,  2*k*(wc^2-1),  k*(1 - sqrt(2)*wc + wc^2)]

2nd-order high-pass Butterworth
    b = [k,  -2*k,  k]
    a = [1,  2*k*(wc^2-1),  k*(1 - sqrt(2)*wc + wc^2)]

State update (Direct Form II Transposed, per biquad section)
    w[n] = x[n] - a1*w1 - a2*w2
    y[n] = b0*w[n] + b1*w1 + b2*w2
    (advance state: w2 <- w1, w1 <- w[n])
"""

from __future__ import annotations

import math


class _Biquad:
    """Single second-order IIR section (Direct Form II Transposed).

    Args:
        b: Numerator coefficients ``[b0, b1, b2]``.
        a: Denominator coefficients ``[1, a1, a2]`` (a[0] is normalised to 1).
    """

    __slots__ = ("b0", "b1", "b2", "a1", "a2", "_w1", "_w2")

    def __init__(self, b: list[float], a: list[float]) -> None:
        self.b0 = b[0]
        self.b1 = b[1]
        self.b2 = b[2]
        self.a1 = a[1]
        self.a2 = a[2]
        self._w1: float = 0.0
        self._w2: float = 0.0

    def process(self, x: float) -> float:
        """Process one sample and return the filtered output."""
        w = x - self.a1 * self._w1 - self.a2 * self._w2
        y = self.b0 * w + self.b1 * self._w1 + self.b2 * self._w2
        self._w2 = self._w1
        self._w1 = w
        return y


def _make_highpass(fc: float, fs: float) -> _Biquad:
    """Compute biquad coefficients for a 2nd-order Butterworth high-pass filter.

    Args:
        fc: Cut-off frequency in Hz.
        fs: Sampling frequency in Hz.

    Returns:
        Configured :class:`_Biquad` section.
    """
    wc = math.tan(math.pi * fc / fs)
    k = 1.0 / (1.0 + math.sqrt(2.0) * wc + wc * wc)
    b = [k, -2.0 * k, k]
    a = [1.0, 2.0 * k * (wc * wc - 1.0), k * (1.0 - math.sqrt(2.0) * wc + wc * wc)]
    return _Biquad(b, a)


def _make_lowpass(fc: float, fs: float) -> _Biquad:
    """Compute biquad coefficients for a 2nd-order Butterworth low-pass filter.

    Args:
        fc: Cut-off frequency in Hz.
        fs: Sampling frequency in Hz.

    Returns:
        Configured :class:`_Biquad` section.
    """
    wc = math.tan(math.pi * fc / fs)
    k = 1.0 / (1.0 + math.sqrt(2.0) * wc + wc * wc)
    b = [k * wc * wc, 2.0 * k * wc * wc, k * wc * wc]
    a = [1.0, 2.0 * k * (wc * wc - 1.0), k * (1.0 - math.sqrt(2.0) * wc + wc * wc)]
    return _Biquad(b, a)


class ECGFilter:
    """Online bandpass ECG filter: 2nd-order HP cascaded with 2nd-order LP.

    Default parameters target Polar H10 ECG (fs=130 Hz, pass-band 0.5–40 Hz).
    All processing is sample-by-sample with no buffering, making this suitable
    for real-time streaming.

    Args:
        sampling_rate_hz: ADC sampling rate in Hz (default 130).
        low_hz: High-pass cut-off frequency in Hz (default 0.5).
        high_hz: Low-pass cut-off frequency in Hz (default 40.0).

    Example::

        filt = ECGFilter()
        for raw in ecg_samples:
            filtered = filt.process(raw)
    """

    def __init__(
        self,
        sampling_rate_hz: int = 130,
        low_hz: float = 0.5,
        high_hz: float = 40.0,
    ) -> None:
        fs = float(sampling_rate_hz)
        self._hp = _make_highpass(low_hz, fs)
        self._lp = _make_lowpass(high_hz, fs)

    def process(self, ecg_uv: float) -> float:
        """Process one sample and return the bandpass-filtered value.

        Args:
            ecg_uv: Raw ECG amplitude in microvolts (or arbitrary units).

        Returns:
            Filtered ECG amplitude in the same units.
        """
        after_hp = self._hp.process(ecg_uv)
        return self._lp.process(after_hp)
