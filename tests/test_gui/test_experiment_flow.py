"""Tests for experiment flow sequencing and counterbalancing."""

from __future__ import annotations

from src.gui.experiment_flow import Condition, PhaseName, build_phase_plan, get_condition_order


def test_condition_order_counterbalance() -> None:
    assert get_condition_order(1) == (Condition.TARGET, Condition.CONTROL)
    assert get_condition_order(2) == (Condition.CONTROL, Condition.TARGET)


def test_phase_plan_contains_required_structure() -> None:
    plan = build_phase_plan(session_number=1, rest_seconds=120, hrfb_seconds=900, break_seconds=120)
    assert len(plan) == 7
    assert plan[0].name == PhaseName.REST_PRE_1
    assert plan[1].condition == Condition.TARGET
    assert plan[5].condition == Condition.CONTROL
