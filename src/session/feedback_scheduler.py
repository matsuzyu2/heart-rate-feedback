"""Absolute-time scheduler for fixed-interval feedback loops."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]
StepHandler = Callable[[float], Awaitable[None]]


class AbsoluteIntervalScheduler:
    """Execute callbacks on absolute interval boundaries.

    This avoids interval drift caused by callback processing duration.
    """

    def __init__(
        self,
        interval_seconds: float,
        *,
        clock: Clock | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self._clock = clock or asyncio.get_running_loop().time
        self._sleep = sleep or asyncio.sleep

    async def run_steps(self, step_count: int, on_step: StepHandler) -> None:
        """Run a fixed number of interval callbacks.

        Args:
            step_count: Number of intervals to execute.
            on_step: Async callback called at each target boundary.
        """
        next_time = self._clock() + self.interval_seconds
        for _ in range(step_count):
            now = self._clock()
            await self._sleep(max(0.0, next_time - now))
            await on_step(next_time)
            next_time += self.interval_seconds
