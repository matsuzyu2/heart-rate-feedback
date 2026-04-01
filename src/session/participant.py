"""Participant persistence model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Participant:
    """Participant metadata persisted across sessions."""

    participant_id: str
    group: str
    created_at: str
    sessions_completed: list[int] = field(default_factory=list)
    notes: str = ""
