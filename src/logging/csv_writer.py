"""CSV writing utility with automatic header initialization."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


class CSVWriter:
    """Append-only CSV writer with deterministic header behavior."""

    def __init__(self, file_path: Path, header: list[str]) -> None:
        self.file_path = file_path
        self.header = header
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with self.file_path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(self.header)

    def write_row(self, row: list[Any]) -> None:
        """Append one row to CSV."""
        with self.file_path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(row)
