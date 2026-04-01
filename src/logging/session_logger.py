"""Session-level CSV writers for raw ECG, heartbeat, and feedback events."""

from __future__ import annotations

from pathlib import Path

from src.logging.csv_writer import CSVWriter


class SessionLogger:
    """Container of per-session file writers."""

    def __init__(self, session_dir: Path) -> None:
        self.ecg_raw = CSVWriter(
            file_path=session_dir / "ecg_raw.csv",
            header=["timestamp_ns", "ecg_uv"],
        )
        self.heartbeats = CSVWriter(
            file_path=session_dir / "heartbeats.csv",
            header=["beat_id", "timestamp_ns", "rr_interval_ms", "heart_rate_bpm"],
        )
        self.feedback_events = CSVWriter(
            file_path=session_dir / "feedback_events.csv",
            header=[
                "system_time_ns",
                "avg_hr_bpm",
                "prev_avg_hr_bpm",
                "hr_trend",
                "feedback_type",
                "condition",
                "reward_accumulated",
            ],
        )
