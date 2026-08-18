"""Tests for intake commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


def _intake_model(**overrides) -> MagicMock:
    """A fake IntakeWorkItem: only `.model_dump()` is used by the commands."""
    payload = {
        "id": "intake-1",
        "issue": "issue-1",
        "status": -2,
        "created_at": "2026-08-18T10:00:00Z",
        "issue_detail": {"id": "issue-1", "name": "Bug report", "priority": "high"},
    }
    payload.update(overrides)
    m = MagicMock()
    m.model_dump.return_value = payload
    return m


@patch("planecli.commands.intake.output")
@patch("planecli.commands.intake.paginate_all_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.get_workspace", return_value="ws")
@patch("planecli.commands.intake.get_client")
async def test_intake_ls_paginates_and_enriches(
    mock_client, mock_ws, mock_resolve, mock_paginate, mock_output
):
    from planecli.commands.intake import INTAKE_COLUMNS, list_

    mock_resolve.return_value = {"id": "p1", "identifier": "ABC", "intake_view": True}
    mock_paginate.return_value = [_intake_model(), _intake_model(id="intake-2", issue="issue-2")]

    await list_(project="ABC", json=True)

    mock_paginate.assert_awaited_once_with(mock_client.return_value.intake.list, "ws", "p1")
    data, columns = mock_output.call_args[0]
    assert columns is INTAKE_COLUMNS
    assert [d["issue_id"] for d in data] == ["issue-1", "issue-2"]
    assert data[0]["status"] == "pending"
    assert mock_output.call_args[1]["as_json"] is True


@patch("planecli.commands.intake.output")
@patch("planecli.commands.intake.paginate_all_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.get_workspace", return_value="ws")
@patch("planecli.commands.intake.get_client")
async def test_intake_ls_empty_queue_still_outputs_empty_list(
    mock_client, mock_ws, mock_resolve, mock_paginate, mock_output
):
    """No client-side intake_view gate: an empty API result is rendered as [] (JSON), not skipped."""
    from planecli.commands.intake import list_

    mock_resolve.return_value = {"id": "p1", "identifier": "ABC", "intake_view": False}
    mock_paginate.return_value = []

    await list_(project="ABC", json=True)

    mock_paginate.assert_awaited_once()
    assert mock_output.call_args[0][0] == []
    assert mock_output.call_args[1]["as_json"] is True


@patch("planecli.commands.intake.output")
@patch("planecli.commands.intake.paginate_all_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.resolve_project_async", new_callable=AsyncMock)
@patch("planecli.commands.intake.get_workspace", return_value="ws")
@patch("planecli.commands.intake.get_client")
async def test_intake_ls_api_error_becomes_planecli_error(
    mock_client, mock_ws, mock_resolve, mock_paginate, mock_output
):
    from plane.errors import HttpError

    from planecli.commands.intake import list_
    from planecli.exceptions import PlaneCLIError

    mock_resolve.return_value = {"id": "p1", "identifier": "ABC"}
    mock_paginate.side_effect = HttpError("Not Found", 404)

    with pytest.raises(PlaneCLIError) as exc:
        await list_(project="ABC")
    assert exc.value.exit_code == 4
    mock_output.assert_not_called()
