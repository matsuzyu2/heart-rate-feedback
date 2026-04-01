"""Tests for TOML settings parsing."""

from __future__ import annotations

from pathlib import Path

from src.config.settings import load_settings


def test_load_settings_parses_trigger_and_device_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.toml"
    config_path.write_text(
        """
[app]
data_dir = "data"
polar_device_id = "D1948025"

[trigger]
reset_pulse_seconds = 0.05
session_start_code = 21
session_end_code = 22
phase_start_code = 23
phase_end_code = 24

[devices.actichamp]
enabled = true
serial_port = "COM7"
serial_baudrate = 115200

[devices.cognionics]
enabled = true
zmq_address = "tcp://127.0.0.1:50001"
serial_port = "COM8"
serial_baudrate = 57600

[devices.lsl]
enabled = true
stream_name = "TEST_STREAM"
source_id = "test_source"
""",
        encoding="utf-8",
    )

    settings = load_settings(config_path=config_path)
    assert settings.trigger.reset_pulse_seconds == 0.05
    assert settings.trigger.session_start_code == 21
    assert settings.trigger.session_end_code == 22
    assert settings.trigger.phase_start_code == 23
    assert settings.trigger.phase_end_code == 24

    assert settings.actichamp.enabled is True
    assert settings.actichamp.serial_port == "COM7"
    assert settings.cognionics.enabled is True
    assert settings.cognionics.zmq_address == "tcp://127.0.0.1:50001"
    assert settings.lsl.enabled is True
    assert settings.lsl.stream_name == "TEST_STREAM"
