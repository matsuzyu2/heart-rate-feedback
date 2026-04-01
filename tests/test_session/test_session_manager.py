"""Tests for longitudinal participant and session persistence."""

from __future__ import annotations

import json

from src.session.session_manager import SessionManager


def test_participant_persistence_and_history(tmp_path) -> None:
    manager = SessionManager(data_dir=tmp_path)

    participant = manager.ensure_participant("P001", "DR")
    assert participant.participant_id == "P001"
    assert participant.group == "DR"

    manager.create_session_meta(
        participant_id="P001",
        session_number=1,
        condition_order=["target", "control"],
        polar_device_id="D1948025",
    )
    manager.finalize_session(
        participant_id="P001",
        session_number=1,
        clock_sync={
            "polar_first_timestamp_ns": 100,
            "system_time_ns_at_first_sample": 200,
            "note": "test",
        },
    )

    participant_payload = json.loads((tmp_path / "P001" / "participant.json").read_text())
    assert participant_payload["sessions_completed"] == [1]

    history = manager.get_session_history("P001")
    assert len(history) == 1
    assert history[0]["session_number"] == 1
    assert history[0]["condition_order"] == ["target", "control"]


def test_phase_lifecycle_is_persisted(tmp_path) -> None:
    manager = SessionManager(data_dir=tmp_path)
    manager.ensure_participant("P001", "UR")
    manager.create_session_meta(
        participant_id="P001",
        session_number=2,
        condition_order=["control", "target"],
        polar_device_id="D1948025",
    )

    manager.begin_phase(
        participant_id="P001",
        session_number=2,
        phase_name="rest_pre_1",
        started_elapsed_sec=0.0,
    )
    manager.end_phase(
        participant_id="P001",
        session_number=2,
        phase_name="rest_pre_1",
        ended_elapsed_sec=120.0,
    )

    payload = json.loads(
        (tmp_path / "P001" / "session_002" / "session_meta.json").read_text(encoding="utf-8")
    )
    assert len(payload["phases"]) == 1
    phase = payload["phases"][0]
    assert phase["phase"] == "rest_pre_1"
    assert phase["started_elapsed_sec"] == 0.0
    assert phase["ended_elapsed_sec"] == 120.0
    assert phase["started_at"] is not None
    assert phase["ended_at"] is not None
