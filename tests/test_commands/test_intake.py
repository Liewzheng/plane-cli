"""Tests for intake commands."""

from __future__ import annotations

import pytest

from planecli.commands.intake import (
    INTAKE_PRIORITIES,
    _enrich_intake,
    _normalize_priority,
)
from planecli.exceptions import ValidationError


@pytest.mark.parametrize("priority", INTAKE_PRIORITIES)
def test_normalize_priority_canonical_values(priority: str) -> None:
    """Canonical priorities pass through unchanged."""
    assert _normalize_priority(priority) == priority


@pytest.mark.parametrize(
    ("value", "expected"),
    [("URGENT", "urgent"), ("  High ", "high"), ("None", "none")],
)
def test_normalize_priority_casing_and_whitespace(value: str, expected: str) -> None:
    assert _normalize_priority(value) == expected


@pytest.mark.parametrize("value", ["urgnet", "1", "", "critical"])
def test_normalize_priority_invalid_raises(value: str) -> None:
    """Invalid priorities raise ValidationError listing the valid values."""
    with pytest.raises(ValidationError) as exc:
        _normalize_priority(value)
    assert "urgent" in (exc.value.hint or "")


def test_enrich_intake_flattens_issue_detail_and_maps_status() -> None:
    data = {
        "id": "intake-1",
        "issue": "issue-1",
        "status": -2,
        "issue_detail": {"id": "issue-1", "name": "Bug report", "priority": "high"},
    }
    result = _enrich_intake(data)
    assert result["name"] == "Bug report"
    assert result["priority"] == "high"
    assert result["issue_id"] == "issue-1"
    assert result["status"] == "pending"


@pytest.mark.parametrize(
    ("code", "label"),
    [(-2, "pending"), (-1, "rejected"), (0, "snoozed"), (1, "accepted"), (2, "duplicate")],
)
def test_enrich_intake_status_labels(code: int, label: str) -> None:
    assert _enrich_intake({"status": code, "issue_detail": {"name": "x"}})["status"] == label


def test_enrich_intake_handles_missing_issue_detail_and_unknown_status() -> None:
    result = _enrich_intake(
        {"id": "intake-1", "issue": "issue-1", "status": 99, "issue_detail": None}
    )
    assert result["name"] == ""
    assert result["priority"] == "none"
    assert result["issue_id"] == "issue-1"  # falls back to top-level `issue`
    assert result["status"] == "99"  # unknown code is shown raw, not hidden


def test_enrich_intake_issue_id_falls_back_to_issue_detail_id() -> None:
    result = _enrich_intake({"issue": None, "issue_detail": {"id": "issue-9", "name": "n"}})
    assert result["issue_id"] == "issue-9"


def test_enrich_intake_none_status_renders_empty() -> None:
    assert _enrich_intake({"status": None, "issue_detail": None})["status"] == ""
