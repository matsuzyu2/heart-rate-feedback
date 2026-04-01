"""Unified trigger event logger."""

from __future__ import annotations

from pathlib import Path

from src.logging.csv_writer import CSVWriter


class TriggerLogger:
    """Write trigger events into one unified CSV file."""

    def __init__(self, file_path: Path) -> None:
        self._writer = CSVWriter(
            file_path=file_path,
            header=["system_time_ns", "device", "trigger_value", "annotation", "success"],
        )

    def log(
        self,
        system_time_ns: int,
        device: str,
        trigger_value: int,
        annotation: str,
        success: bool,
    ) -> None:
        """Persist one trigger send result."""
        self._writer.write_row([system_time_ns, device, trigger_value, annotation, success])
