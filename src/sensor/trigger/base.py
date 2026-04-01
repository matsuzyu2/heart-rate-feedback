"""Trigger interfaces and dispatcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from src.logging.trigger_logger import TriggerLogger


class TriggerDevice(Protocol):
    """Protocol for EEG trigger devices."""

    name: str

    async def send(self, trigger_value: int, reset_pulse_seconds: float) -> bool:
        """Send one trigger pulse and reset."""


@dataclass(frozen=True)
class TriggerResult:
    """Single trigger send result."""

    device: str
    success: bool


class TriggerDispatcher:
    """Send triggers to multiple devices with one shared timestamp."""

    def __init__(self, devices: list[TriggerDevice], logger: TriggerLogger) -> None:
        self._devices = devices
        self._logger = logger

    async def send_all(
        self,
        trigger_value: int,
        annotation: str,
        system_time_ns: int,
        reset_pulse_seconds: float,
    ) -> list[TriggerResult]:
        """Send trigger to all devices concurrently."""
        tasks = [
            asyncio.create_task(d.send(trigger_value, reset_pulse_seconds))
            for d in self._devices
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        results: list[TriggerResult] = []
        for device, raw in zip(self._devices, raw_results):
            success = isinstance(raw, bool) and raw
            result = TriggerResult(device=device.name, success=success)
            results.append(result)
            self._logger.log(
                system_time_ns=system_time_ns,
                device=device.name,
                trigger_value=trigger_value,
                annotation=annotation,
                success=success,
            )
        return results
