"""Participant form model and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Group(StrEnum):
    """Participant group assignment."""

    UR = "UR"
    DR = "DR"


@dataclass(frozen=True)
class ParticipantInput:
    """Normalized participant/session input from GUI."""

    participant_id: str
    group: Group
    session_number: int


def validate_participant_id(participant_id: str) -> bool:
    """Validate participant IDs like P001."""
    if len(participant_id) != 4:
        return False
    if not participant_id.startswith("P"):
        return False
    return participant_id[1:].isdigit()
