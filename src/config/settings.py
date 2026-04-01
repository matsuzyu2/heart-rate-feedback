"""Configuration loading from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from src.config.defaults import (
    ActiChampDeviceDefaults,
    CognionicsDeviceDefaults,
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATA_DIR,
    DEFAULT_POLAR_DEVICE_ID,
    LSLDeviceDefaults,
    ProcessingDefaults,
    TimingDefaults,
    TriggerDefaults,
)


@dataclass(frozen=True)
class AppSettings:
    """Top-level application settings."""

    data_dir: Path
    polar_device_id: str
    processing: ProcessingDefaults
    timing: TimingDefaults
    trigger: TriggerDefaults
    actichamp: ActiChampDeviceDefaults
    cognionics: CognionicsDeviceDefaults
    lsl: LSLDeviceDefaults


def _section(cfg: dict[str, Any], key: str) -> dict[str, Any]:
    section = cfg.get(key)
    if isinstance(section, dict):
        return section
    return {}


def load_settings(config_path: Path | None = None) -> AppSettings:
    """Load app settings from TOML.

    Args:
        config_path: Optional path to config TOML.

    Returns:
        Parsed AppSettings.
    """
    effective_path = config_path or DEFAULT_CONFIG_PATH
    parsed: dict[str, Any] = {}
    if effective_path.exists():
        parsed = tomllib.loads(effective_path.read_text(encoding="utf-8"))

    app = _section(parsed, "app")
    processing = _section(parsed, "processing")
    timing = _section(parsed, "timing")
    trigger = _section(parsed, "trigger")
    devices = _section(parsed, "devices")
    actichamp = _section(devices, "actichamp")
    cognionics = _section(devices, "cognionics")
    lsl = _section(devices, "lsl")

    return AppSettings(
        data_dir=Path(str(app.get("data_dir", DEFAULT_DATA_DIR))),
        polar_device_id=str(app.get("polar_device_id", DEFAULT_POLAR_DEVICE_ID)),
        processing=ProcessingDefaults(
            sampling_rate_hz=int(processing.get("sampling_rate_hz", 130)),
            bandpass_low_hz=float(processing.get("bandpass_low_hz", 0.5)),
            bandpass_high_hz=float(processing.get("bandpass_high_hz", 40.0)),
            refractory_period_ms=int(processing.get("refractory_period_ms", 180)),
            trend_threshold_bpm=float(processing.get("trend_threshold_bpm", 1.0)),
            rr_outlier_threshold_bpm=float(
                processing.get("rr_outlier_threshold_bpm", 10.0)
            ),
        ),
        timing=TimingDefaults(
            rest_seconds=int(timing.get("rest_seconds", 120)),
            hrfb_seconds=int(timing.get("hrfb_seconds", 900)),
            break_seconds=int(timing.get("break_seconds", 120)),
            feedback_interval_seconds=float(
                timing.get("feedback_interval_seconds", 5.0)
            ),
        ),
        trigger=TriggerDefaults(
            actichamp_code=int(trigger.get("actichamp_code", 1)),
            cognionics_code=int(trigger.get("cognionics_code", 100)),
            reset_pulse_seconds=float(trigger.get("reset_pulse_seconds", 0.02)),
            session_start_code=int(trigger.get("session_start_code", 10)),
            session_end_code=int(trigger.get("session_end_code", 11)),
            phase_start_code=int(trigger.get("phase_start_code", 12)),
            phase_end_code=int(trigger.get("phase_end_code", 13)),
        ),
        actichamp=ActiChampDeviceDefaults(
            enabled=bool(actichamp.get("enabled", False)),
            serial_port=str(actichamp.get("serial_port", "COM4")),
            serial_baudrate=int(actichamp.get("serial_baudrate", 2000000)),
        ),
        cognionics=CognionicsDeviceDefaults(
            enabled=bool(cognionics.get("enabled", False)),
            zmq_address=str(cognionics.get("zmq_address", "tcp://127.0.0.1:50000")),
            serial_port=str(cognionics.get("serial_port", "COM10")),
            serial_baudrate=int(cognionics.get("serial_baudrate", 9600)),
        ),
        lsl=LSLDeviceDefaults(
            enabled=bool(lsl.get("enabled", False)),
            stream_name=str(lsl.get("stream_name", "HRFB_Markers")),
            source_id=str(lsl.get("source_id", "hrfb_marker")),
        ),
    )
