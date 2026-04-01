"""Tests for absolute-time feedback scheduler."""

from __future__ import annotations

import pytest

from src.session.feedback_scheduler import AbsoluteIntervalScheduler


@pytest.mark.asyncio
async def test_scheduler_does_not_drift_with_processing_delay() -> None:
    now = 0.0
    emitted: list[float] = []

    def fake_clock() -> float:
        return now

    async def fake_sleep(duration: float) -> None:
        nonlocal now
        now += duration

    async def on_step(target_time: float) -> None:
        nonlocal now
        emitted.append(target_time)
        now += 0.2

    scheduler = AbsoluteIntervalScheduler(
        interval_seconds=5.0,
        clock=fake_clock,
        sleep=fake_sleep,
    )
    await scheduler.run_steps(step_count=3, on_step=on_step)

    assert emitted == [5.0, 10.0, 15.0]
