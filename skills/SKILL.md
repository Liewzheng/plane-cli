---
name: planecli
description: "Manage Plane.so project management via the planecli CLI — list, create, update, and search work items, projects, cycles/sprints, modules, labels, states, documents, intake queues, and comments. ALWAYS use this skill when the user mentions Plane, Plane.so, planecli, or references work item identifiers like ABC-123, FE-234, MOB-45. Also invoke when the user asks to manage tasks, issues, sprints, backlogs, or project boards AND either explicitly mentions Plane or the project context indicates Plane is the tool in use. Do NOT use for other project management tools (Jira, Linear, Asana, Trello, Azure DevOps Boards)."
allowed-tools: Bash(planecli *)
metadata:
  author: Patrick Alves
  version: "1.5"
---

# PlaneCLI

CLI for [Plane.so](https://plane.so) project management. Installed as `planecli`.

## Key Concepts

- **Fuzzy resolution**: All resource arguments (projects, states, labels, users, work items) accept names, identifiers (e.g. `ABC-123`), or UUIDs. Fuzzy matching with 60% threshold finds close matches.
- **"me" shortcut**: Pass `me` as the assignee value to reference the authenticated user.
- **Output**: Always pass `--json` to get structured JSON output. JSON is the preferred output format.
- **Caching**: Responses are cached on disk. Pass `--no-cache` to bypass or run `planecli cache clear` to reset.
- **Project scoping**: Most commands require `-p PROJECT`. Work items with identifier format (ABC-123) auto-resolve across projects.

## Quick Reference

### Identity & Configuration

```bash
planecli whoami --json          # Show authenticated user
planecli configure                          # Interactive setup
planecli users ls --json        # List workspace members
```

### Work Items (most common)

```bash
# List / filter
planecli wi ls -p "Project" --state "In Progress" --assignee me --limit 10 --json
planecli wi ls -p "Project" --labels "bug,critical" --sort updated --json

# Create
planecli wi create "Title" -p "Project" --assign me --priority urgent --state "Todo" --json
planecli wi create "Sub-task" --parent ABC-123 --assign "Patrick" --labels "backend" --json

# Create with description (-d / --description). The value is stored as HTML, NOT markdown
# (see Gotchas). For long/multiline bodies, write HTML to a file and pipe it in:
planecli wi create "Title" -p "Project" -d "<p>Short description.</p>" --json
planecli wi create "Title" -p "Project" -d "$(cat /tmp/body.html)" --json   # long/rich body

# Update
planecli wi update ABC-123 --state "Done" --priority none --json
planecli wi update ABC-123 --assign "Patrick" --labels "bug,urgent" --json

# Other
planecli wi show ABC-123 --json                     # Bundles comments (comments: [...] / [] / null)
planecli wi show ABC-123 --no-comments --json        # Skip the comment fetch
planecli wi assign ABC-123 --json                   # Assign to yourself
planecli wi assign ABC-123 --assign "Name" --json   # Assign to someone
planecli wi search "login bug" -p "Project" --json
planecli wi delete ABC-123
```

### Projects

```bash
planecli project ls --state started --sort created --json
planecli project show "Frontend" --json
planecli project create "New Project" -i "NP" -d "Description" --json
planecli project update "Name" --name "New Name" --json
planecli project delete "Name"
```

### Cycles (Sprints)

```bash
planecli cycle ls -p "Project" --json
planecli cycle create "Sprint 1" -p "Project" --start-date 2026-02-17 --end-date 2026-03-02 --json
planecli cycle add-item "Sprint 1" ABC-123 -p "Project"
planecli cycle remove-item "Sprint 1" ABC-123 -p "Project"
planecli cycle items "Sprint 1" -p "Project" --json
```

### Intake

```bash
# List the queue. The Issue ID column is what accept/decline/delete take (NOT the Intake ID)
planecli intake ls -p "Project" --json

# Create a queued item (priority: none, low, medium, high, urgent)
planecli intake create "Login button broken" -p "Project" -d "Steps to reproduce..." -P high --json

# Triage - requires the project Admin role
planecli intake accept <issue-uuid> -p "Project" --json
planecli intake decline <issue-uuid> -p "Project" --json

# Destructive: for any status other than 'accepted' this also deletes the work item
planecli intake delete <issue-uuid> -p "Project"

# Is intake enabled for the project?
planecli intake enabled "Project" --json
```

### Modules, Labels, States, Documents, Comments

```bash
# Modules (--status: backlog, planned, in-progress, paused, completed, cancelled)
planecli module ls -p "Project" --json
planecli module create "Auth" -p "Project" -d "Login flows" --status in-progress --json
planecli module update "Auth" -p "Project" --status completed --json

# Labels
planecli label ls -p "Project" --json
planecli label create "urgent" -p "Project" --color "#FF0000" --json

# States (groups: backlog, unstarted, started, completed, cancelled)
planecli state ls -p "Project" --group started --json
planecli state create "In Review" -p "Project" --group started --color "#FFA500" --json

# Documents
planecli doc ls -p "Project" --json
planecli doc create --title "Spec" --content "## Details..." -p "Project" --json

# Comments
planecli comment ls ABC-123 --json
planecli comment create ABC-123 --body "Fixed in PR #456" --json
```

## Command Aliases

| Full | Aliases |
|---|---|
| `work-item` | `wi`, `issues`, `issue` |
| `project` | `projects` |
| `document` | `doc`, `docs`, `documents` |
| `comment` | `comments` |
| `module` | `modules` |
| `label` | `labels` |
| `state` | `states` |
| `cycle` | `cycles` |
| `user` | `users` |
| `list` | `ls` |
| `show` | `read` |
| `create` | `new` |

## Priority Values

`urgent` (1), `high` (2), `medium` (3), `low` (4), `none` (0). Accept names or numbers.

## Gotchas

- **Descriptions are HTML, not markdown.** The `-d` / `--description` flag on `wi create` and `wi update` stores the value verbatim inside the Plane editor's HTML, without escaping it. Markdown is NOT converted: `## Title` and backticks render literally in the UI. Pass HTML instead — `<h2>`, `<p>`, `<ul>`, `<code>` and `<pre><code>` all survive. To reuse a markdown source, convert it first (any md-to-html converter) and pass `-d "$(cat body.html)"`; a file is far more reliable than a huge inline string. Plane prepends an empty `<p></p>` to the stored value, which is cosmetic. This applies to work items only: `intake create -d` HTML-escapes its input, so tags show up as text there.
- **Verify the rendering on the FIRST item, before creating the rest.** `planecli wi show ABC-123 --no-cache --json | jq -r .description_html` must contain real tags (`<h2>`, `<pre>`) and not `##` or backticks. A non-empty description proves nothing — malformed input is stored happily.
- **Never conclude "creation failed" from your own output pipeline.** `wi create` prints the created item as JSON, so a broken `jq` filter over that output looks exactly like a failed create. Confirm against the server before retrying: `planecli wi ls -p PROJECT --no-cache --json | jq -r '.[] | select(.parent=="<parent-uuid>") | .sequence_id'`. There is no idempotency key — retrying a create that actually succeeded silently duplicates the work item.
- **`wi show` occasionally returns non-JSON.** In one 17-item verification sweep, 4 calls failed with `jq: parse error: Invalid numeric literal`; repeating the identical call succeeded every time. Treat it as transient and retry once before investigating.
- **The `*_names` fields hold UUIDs, not names.** `assignee_names`, `label_names`, `label_detail_names` and `state_detail_name` from `wi show` return raw UUIDs despite what they are called. To check a bulk result, build lookup maps first with `label ls`, `state ls` and `users ls`, or read `priority` and `name` from `wi ls`, which are human-readable.
- **`sequence_id` shape differs between commands.** `wi show`/`wi create` return it as an integer (`204`); `wi ls` returns it already prefixed as a string (`"PIPERAG-204"`). Don't re-prefix the list value (you'd get `PIPERAG-PIPERAG-204`). To build an identifier, use `sequence_id` directly from `wi ls`, or `"{project_identifier}-{sequence_id}"` from `wi show`.
- **`wi show` bundles comments, and can degrade to `comments: null`.** `comments` is `[]` when there are none, a list when there are, or `null` if the comment fetch failed — the work item itself still returns and the command still exits 0 (a comment fetch failure never fails `wi show`). Check for `null` explicitly if your script needs to distinguish "no comments" from "couldn't load comments". Pass `--no-comments` to skip the fetch (then the `comments` key is absent from JSON entirely).
- **Intake mutations take the work item UUID, not the intake ID.** `intake ls` returns both: `id` (the queue wrapper) and `issue_id` (the work item). `accept`, `decline`, and `delete` all take `issue_id` — passing the wrapper `id` fails.
- **`intake accept` / `intake decline` need the project Admin role.** The API answers `200` with the record unchanged for lower roles; the CLI detects that and exits `4` with "the intake status was not changed". A `0` exit means the triage really happened.
- **`intake delete` is not just a dequeue.** For any status other than `accepted` it permanently deletes the underlying work item too. There is no confirmation prompt and no undo — read the status from `intake ls` first, or use `intake decline` when you only want it out of the queue.

## Common Patterns

```bash
# Get my in-progress items across all projects
planecli wi ls --assignee me --state "In Progress" --json

# JSON output piped to jq
planecli wi ls -p "Project" --json | jq '.[].name'

# Create sub-issue under parent
planecli wi create "Sub-task" --parent ABC-123 -p "Project" --json

# Bulk check: list then update
planecli wi ls -p "Project" --state "In Review" --json
planecli wi update ABC-456 --state "Done" --json
```

### Bulk create with rich descriptions

One file per item, convert to HTML, prove the first one renders, then create the rest and
count what landed on the server.

```bash
# 1. write one body per item (01.md, 02.md, ...) and convert them to HTML
npx marked -i 01.md -o 01.html          # or any md-to-html converter

# 2. create the FIRST item and inspect its stored HTML before going further
planecli wi create "First title" -p "Project" --parent ABC-1 --assign "Name" \
  --state "Todo" --priority high --labels "bug,backend" -d "$(cat 01.html)" --json
planecli wi show ABC-2 --no-cache --json | jq -r .description_html   # expect <h2>, <pre>

# 3. create the remaining items, then verify the whole batch by parent
planecli wi ls -p "Project" --no-cache --json \
  | jq -r '.[] | select(.parent=="<parent-uuid>") | "\(.sequence_id) \(.priority) \(.name)"'
```

## Full Command Reference

For complete flag details on every command, see [references/command-reference.md](references/command-reference.md).
