"""Tests for trigger dispatch behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.logging.trigger_logger import TriggerLogger
from src.sensor.trigger.base import TriggerDispatcher


class _FakeDevice:
    def __init__(self, name: str, success: bool) -> None:
        self.name = name
        self._success = success
        self.calls: list[tuple[int, float]] = []

    async def send(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        self.calls.append((trigger_value, reset_pulse_seconds))
        return self._success


@pytest.mark.asyncio
async def test_dispatcher_uses_single_timestamp_for_all_rows(tmp_path: Path) -> None:
    logger = TriggerLogger(tmp_path / "trigger_log.csv")
    d1 = _FakeDevice("actichamp", True)
    d2 = _FakeDevice("cognionics", False)
    dispatcher = TriggerDispatcher(devices=[d1, d2], logger=logger)

    ts = 123456789
    results = await dispatcher.send_all(
        trigger_value=100,
        annotation="phase_start",
        system_time_ns=ts,
        reset_pulse_seconds=0.02,
    )

    assert len(results) == 2
    assert d1.calls == [(100, 0.02)]
    assert d2.calls == [(100, 0.02)]

    lines = (tmp_path / "trigger_log.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert lines[1].startswith("123456789,actichamp,100,phase_start,True")
    assert lines[2].startswith("123456789,cognionics,100,phase_start,False")
