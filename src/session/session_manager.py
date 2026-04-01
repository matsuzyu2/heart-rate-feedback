"""Participant/session metadata persistence utilities."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.session.participant import Participant


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


class SessionManager:
    """Data directory management for longitudinal sessions."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ensure_participant(self, participant_id: str, group: str) -> Participant:
        """Create or load participant record."""
        participant_path = self._participant_path(participant_id)
        if participant_path.exists():
            payload = json.loads(participant_path.read_text(encoding="utf-8"))
            return Participant(**payload)

        participant = Participant(
            participant_id=participant_id,
            group=group,
            created_at=_now_iso(),
        )
        participant_path.parent.mkdir(parents=True, exist_ok=True)
        participant_path.write_text(
            json.dumps(asdict(participant), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return participant

    def create_session_meta(
        self,
        participant_id: str,
        session_number: int,
        condition_order: list[str],
        polar_device_id: str,
    ) -> Path:
        """Initialize session_meta.json."""
        meta = {
            "session_number": session_number,
            "started_at": _now_iso(),
            "ended_at": None,
            "condition_order": condition_order,
            "polar_device_id": polar_device_id,
            "clock_sync": {},
            "phases": [],
        }
        path = self._session_dir(participant_id, session_number) / "session_meta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def append_phase_record(
        self,
        participant_id: str,
        session_number: int,
        phase: dict[str, Any],
    ) -> None:
        """Append one phase record into session_meta.json."""
        path = self._session_dir(participant_id, session_number) / "session_meta.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["phases"].append(phase)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def begin_phase(
        self,
        participant_id: str,
        session_number: int,
        phase_name: str,
        started_elapsed_sec: float,
        condition: str | None = None,
    ) -> None:
        """Append a started phase entry into session_meta.json."""
        phase_payload: dict[str, Any] = {
            "phase": phase_name,
            "started_at": _now_iso(),
            "ended_at": None,
            "started_elapsed_sec": round(started_elapsed_sec, 3),
            "ended_elapsed_sec": None,
        }
        if condition is not None:
            phase_payload["condition"] = condition
        self.append_phase_record(
            participant_id=participant_id,
            session_number=session_number,
            phase=phase_payload,
        )

    def end_phase(
        self,
        participant_id: str,
        session_number: int,
        phase_name: str,
        ended_elapsed_sec: float,
    ) -> None:
        """Mark the latest open phase record as ended."""
        path = self._session_dir(participant_id, session_number) / "session_meta.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        phases = list(payload.get("phases", []))

        for record in reversed(phases):
            if record.get("phase") == phase_name and record.get("ended_at") is None:
                record["ended_at"] = _now_iso()
                record["ended_elapsed_sec"] = round(ended_elapsed_sec, 3)
                path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=True),
                    encoding="utf-8",
                )
                return

        raise ValueError(f"No open phase found for {phase_name}")

    def finalize_session(
        self,
        participant_id: str,
        session_number: int,
        clock_sync: dict[str, int | str] | None = None,
    ) -> None:
        """Finalize session metadata and participant completed list."""
        session_path = self._session_dir(participant_id, session_number) / "session_meta.json"
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        payload["ended_at"] = _now_iso()
        payload["clock_sync"] = clock_sync or {}
        session_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

        participant_path = self._participant_path(participant_id)
        participant_payload = json.loads(participant_path.read_text(encoding="utf-8"))
        sessions = list(participant_payload.get("sessions_completed", []))
        if session_number not in sessions:
            sessions.append(session_number)
        sessions.sort()
        participant_payload["sessions_completed"] = sessions
        participant_path.write_text(
            json.dumps(participant_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def get_session_history(self, participant_id: str) -> list[dict[str, Any]]:
        """Return sorted history rows with session date and condition order."""
        participant_dir = self.data_dir / participant_id
        if not participant_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for session_dir in sorted(participant_dir.glob("session_*")):
            meta_path = session_dir / "session_meta.json"
            if not meta_path.exists():
                continue
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "session_number": payload.get("session_number"),
                    "started_at": payload.get("started_at"),
                    "condition_order": payload.get("condition_order", []),
                }
            )
        return rows

    def get_session_dir(self, participant_id: str, session_number: int) -> Path:
        """Return concrete directory for one participant session."""
        return self._session_dir(participant_id, session_number)

    def _participant_path(self, participant_id: str) -> Path:
        return self.data_dir / participant_id / "participant.json"

    def _session_dir(self, participant_id: str, session_number: int) -> Path:
        return self.data_dir / participant_id / f"session_{session_number:03d}"
