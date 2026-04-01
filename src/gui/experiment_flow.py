"""Experiment flow definitions and phase sequencing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Condition(StrEnum):
    """HRFB condition labels."""

    TARGET = "target"
    CONTROL = "control"


class PhaseName(StrEnum):
    """Fixed phase names for session metadata."""

    REST_PRE_1 = "rest_pre_1"
    HRFB_1 = "hrfb_1"
    REST_POST_1 = "rest_post_1"
    BREAK = "break"
    REST_PRE_2 = "rest_pre_2"
    HRFB_2 = "hrfb_2"
    REST_POST_2 = "rest_post_2"


@dataclass(frozen=True)
class PhasePlan:
    """One phase configuration in the session plan."""

    name: PhaseName
    duration_seconds: int
    condition: Condition | None = None


def get_condition_order(session_number: int) -> tuple[Condition, Condition]:
    """Counter-balance condition order using session parity."""
    if session_number % 2 == 1:
        return (Condition.TARGET, Condition.CONTROL)
    return (Condition.CONTROL, Condition.TARGET)


def build_phase_plan(
    session_number: int,
    rest_seconds: int,
    hrfb_seconds: int,
    break_seconds: int,
) -> list[PhasePlan]:
    """Construct fixed 8-step HRFB session flow."""
    cond1, cond2 = get_condition_order(session_number)
    return [
        PhasePlan(name=PhaseName.REST_PRE_1, duration_seconds=rest_seconds),
        PhasePlan(name=PhaseName.HRFB_1, duration_seconds=hrfb_seconds, condition=cond1),
        PhasePlan(name=PhaseName.REST_POST_1, duration_seconds=rest_seconds),
        PhasePlan(name=PhaseName.BREAK, duration_seconds=break_seconds),
        PhasePlan(name=PhaseName.REST_PRE_2, duration_seconds=rest_seconds),
        PhasePlan(name=PhaseName.HRFB_2, duration_seconds=hrfb_seconds, condition=cond2),
        PhasePlan(name=PhaseName.REST_POST_2, duration_seconds=rest_seconds),
    ]
