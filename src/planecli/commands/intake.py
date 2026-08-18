"""Intake queue commands.

Uses the Plane SDK ``client.intake`` resource (plane-sdk >= 0.2.6).

Plane API notes:
- ``accept``/``decline``/``delete`` take the *work item* UUID (the ``issue`` field of an
  intake item, shown as "Issue ID" by ``intake ls``), NOT the intake wrapper ``id``.
- ``status`` is an integer: -2 pending, -1 rejected, 0 snoozed, 1 accepted, 2 duplicate.
- Whether intake is enabled is decided by the API: ``ls`` returns an empty list and
  mutations return HTTP 400 for projects without intake.
"""

from __future__ import annotations

import html
from typing import Annotated

import cyclopts
from cyclopts import Parameter
from plane.errors import PlaneError

from planecli.api.async_sdk import paginate_all_async, run_sdk
from planecli.api.client import get_client, get_workspace, handle_api_error
from planecli.exceptions import ValidationError
from planecli.formatters import console, output, output_single
from planecli.utils.resolve import resolve_project_async

intake_app = cyclopts.App(
    name=["intake"],
    help="Manage project intake queues.",
)

INTAKE_STATUS_LABELS = {
    -2: "pending",
    -1: "rejected",
    0: "snoozed",
    1: "accepted",
    2: "duplicate",
}

INTAKE_PRIORITIES = ("none", "low", "medium", "high", "urgent")

INTAKE_COLUMNS = [
    ("name", "Name"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("issue_id", "Issue ID"),
]

INTAKE_FIELDS = [
    ("issue_id", "Issue ID"),
    ("id", "Intake ID"),
    ("name", "Name"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("updated_at", "Updated"),
]


def _normalize_priority(value: str) -> str:
    """Normalize and validate a priority. Raises ValidationError on invalid input."""
    key = value.strip().lower()
    if key not in INTAKE_PRIORITIES:
        allowed = ", ".join(INTAKE_PRIORITIES)
        raise ValidationError(
            f"Invalid priority '{value}'.",
            hint=f"Valid values: {allowed}.",
        )
    return key


def _enrich_intake(data: dict) -> dict:
    """Flatten an IntakeWorkItem dict for display: name/priority/issue_id + status label."""
    issue = data.get("issue_detail") or {}
    data["name"] = issue.get("name") or ""
    data["priority"] = issue.get("priority") or "none"
    data["issue_id"] = data.get("issue") or issue.get("id") or ""
    status = data.get("status")
    if status is None:
        data["status"] = ""
    else:
        data["status"] = INTAKE_STATUS_LABELS.get(status, str(status))
    return data


@intake_app.command(name="list", alias="ls")
async def list_(
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
    json: bool = False,
) -> None:
    """List items in a project's intake queue.

    Parameters
    ----------
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    if not proj.get("intake_view"):
        console.print(
            f"[yellow]Project '{proj.get('name', project)}' does not have intake enabled.[/]"
        )
        return

    config = get_config()
    url = _intake_url(config, workspace, proj["id"])
    resp = requests.get(url, headers=_headers(config), timeout=30)
    resp.raise_for_status()
    body = resp.json()

    results = [_enrich_intake(item) for item in body.get("results", [])]
    output(results, INTAKE_COLUMNS, title=f"Intake Queue ({proj.get('identifier', '')})", as_json=json)


@intake_app.command(alias="new")
async def create(
    name: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
    description: Annotated[str | None, Parameter(alias="-d")] = None,
    priority: Annotated[str | None, Parameter(alias="-P")] = None,
    json: bool = False,
) -> None:
    """Create a new intake item in a project's intake queue.

    Parameters
    ----------
    name
        Item title (required).
    project
        Project name, identifier, or UUID. Required.
    description
        Item description. Automatically wrapped in <p> for HTML.
    priority
        Priority: none, low, medium, high, urgent. Default: none.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    if not proj.get("intake_view"):
        from planecli.exceptions import ValidationError
        raise ValidationError(
            f"Project '{proj.get('name', project)}' does not have intake enabled."
        )

    issue = {"name": name, "priority": priority or "none"}
    if description:
        issue["description_html"] = f"<p>{description}</p>"

    config = get_config()
    url = _intake_url(config, workspace, proj["id"])
    resp = requests.post(url, headers=_headers(config), json={"issue": issue}, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    data = _enrich_intake(body)
    output_single(data, INTAKE_FIELDS, title="Intake Item Created", as_json=json)


@intake_app.command
async def accept(
    intake_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
) -> None:
    """Accept (triage) an intake item, converting it to a regular work item.

    Parameters
    ----------
    intake_id
        Intake item ID (UUID). The issue_detail UUID also works.
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.patch(
        url, headers=_headers(config), json={"status": 1}, timeout=30
    )
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} accepted.[/]")


@intake_app.command
async def decline(
    intake_id: str,
    *,
    project: Annotated[str, Parameter(alias="-p")] = None,
) -> None:
    """Decline an intake item.

    Parameters
    ----------
    intake_id
        Intake item ID (UUID). The issue_detail UUID also works.
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.patch(
        url, headers=_headers(config), json={"status": -1}, timeout=30
    )
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} declined.[/]")


@intake_app.command
async def delete(intake_id: str, *, project: Annotated[str, Parameter(alias="-p")] = None) -> None:
    """Delete an intake item.

    Parameters
    ----------
    intake_id
        The issue_detail UUID (the actual issue ID, not the intake wrapper ID).
    project
        Project name, identifier, or UUID. Required.
    """
    import requests

    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    config = get_config()
    url = (
        f"{config.base_url}/api/v1/workspaces/{workspace}"
        f"/projects/{proj['id']}/intake-issues/{intake_id}/"
    )
    resp = requests.delete(url, headers=_headers(config), timeout=30)
    resp.raise_for_status()
    console.print(f"[green]Intake item {intake_id} deleted.[/]")


@intake_app.command
async def enabled(
    project: str,
    *,
    json: bool = False,
) -> None:
    """Check if a project has intake enabled.

    Parameters
    ----------
    project
        Project name, identifier, or UUID.
    """
    try:
        client = get_client()
        workspace = get_workspace()
        proj = await resolve_project_async(project, client, workspace)
    except PlaneError as e:
        raise handle_api_error(e)

    intake_view = proj.get("intake_view", False)
    if json:
        import sys
        sys.stdout.write(f'{{"intake_enabled": {str(intake_view).lower()}, "project_id": "{proj["id"]}"}}\n')
    elif intake_view:
        console.print(f"[green]Intake is enabled[/] for {proj.get('name', project)} (ID: {proj['id']})")
    else:
        console.print(
            f"[yellow]Intake is NOT enabled[/] for {proj.get('name', project)} (ID: {proj['id']})"
        )
