"""Default constants for heart-rate biofeedback configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimingDefaults:
    """Default phase durations in seconds."""

    rest_seconds: int = 120
    hrfb_seconds: int = 900
    break_seconds: int = 120
    feedback_interval_seconds: float = 5.0


@dataclass(frozen=True)
class ProcessingDefaults:
    """Default ECG processing values."""

    sampling_rate_hz: int = 130
    bandpass_low_hz: float = 0.5
    bandpass_high_hz: float = 40.0
    refractory_period_ms: int = 180
    trend_threshold_bpm: float = 1.0
    rr_outlier_threshold_bpm: float = 10.0


@dataclass(frozen=True)
class TriggerDefaults:
    """Default trigger behavior and code mapping."""

    actichamp_code: int = 1
    cognionics_code: int = 100
    reset_pulse_seconds: float = 0.02


DEFAULT_DATA_DIR = Path("data")
DEFAULT_CONFIG_PATH = Path("config/default_config.toml")
DEFAULT_POLAR_DEVICE_ID = "D1948025"
