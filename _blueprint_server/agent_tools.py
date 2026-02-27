"""
agent_tools.py — MCP Tools for the LLM agent.
Provides create_artifact, update_status, validate_all, and run_self_critique.
All writes are validated against the traceability rules before touching the file system.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from config import BLUEPRINT_ROOT
from fs_reader import read_frontmatter, write_frontmatter, patch_frontmatter, read_body
from artifact_index import build_index, ID_PREFIXES
from validate_traceability import validate_traceability, REQUIRED_FIELDS
from logger import tool_call, tool_ok, tool_error, gate_blocked, artifact_created, status_change, validate_result


# ---------------------------------------------------------------------------
# Directory routing per artifact type
# ---------------------------------------------------------------------------

ARTIFACT_WRITE_DIRS: dict[str, Path] = {
    "Goal":     BLUEPRINT_ROOT / "dev_docs" / "brain",
    "Feature":  BLUEPRINT_ROOT / "dev_docs" / "logic",
    "Research": BLUEPRINT_ROOT / "dev_docs" / "brain" / "R_D_Archive",
    "UseCase":  BLUEPRINT_ROOT / "dev_docs" / "logic",
    "Task":     BLUEPRINT_ROOT / "execution" / "backlog",
}

VALID_STATUSES = {"DRAFT", "REVIEW", "APPROVED", "NEEDS_FIX", "BLOCKED", "DONE", "ARCHIVED"}
VALID_TYPES = set(ARTIFACT_WRITE_DIRS.keys())


def _text(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=msg)]


def _err_text(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"❌ Error: {msg}")]


# ---------------------------------------------------------------------------
# Tool implementations (plain async functions — no decorator)
# ---------------------------------------------------------------------------

async def _create_artifact(args: dict) -> list[TextContent]:
    atype    = args.get("type", "")
    aid      = args.get("id", "")
    parent_id = args.get("parent_id") or None
    content  = args.get("content", "")
    metadata = args.get("metadata") or {}

    tool_call("create_artifact", {"type": atype, "id": aid, "parent_id": parent_id or ""})

    if atype not in VALID_TYPES:
        msg = f"Unknown artifact type '{atype}'. Valid: {', '.join(sorted(VALID_TYPES))}"
        tool_error("create_artifact", msg)
        return _err_text(msg)

    idx = build_index()

    if parent_id and parent_id not in idx:
        msg = f"Parent '{parent_id}' not found. Create the parent first."
        tool_error("create_artifact", msg)
        return _err_text(msg)

    # Gate G1: Task needs APPROVED parent UC
    if atype == "Task":
        uc_id = str(metadata.get("parent_uc", parent_id or ""))
        parent = idx.get(uc_id)
        if not parent:
            msg = f"Task requires a valid parent_uc. '{uc_id}' not found."
            gate_blocked("G1", msg)
            return _err_text(msg)
        if parent["meta"].get("status") != "APPROVED":
            msg = (
                f"Cannot create Task: parent UseCase '{uc_id}' has status "
                f"'{parent['meta'].get('status')}'. Must be APPROVED."
            )
            gate_blocked("G1", msg)
            return _err_text(msg)

    # Build full metadata
    full_meta: dict[str, Any] = {
        "id":             aid,
        "status":         "DRAFT",
        "created_at":     datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "revision_count": 1,
    }
    if parent_id:
        parent_type = idx.get(parent_id, {}).get("type", "")
        field_map = {"Goal": "parent_goal", "Feature": "parent_feat", "UseCase": "parent_uc"}
        pfield = field_map.get(parent_type, "origin")
        full_meta[pfield] = parent_id
    full_meta.update(metadata)

    missing = [f for f in REQUIRED_FIELDS.get(atype, []) if not full_meta.get(f)]
    if missing:
        msg = f"Missing required fields for {atype}: {', '.join(missing)}"
        tool_error("create_artifact", msg)
        return _err_text(msg)

    target_dir  = ARTIFACT_WRITE_DIRS[atype]
    target_file = target_dir / f"{aid}.md"
    if target_file.exists():
        msg = f"Artifact '{aid}' already exists. Use update_status to modify."
        tool_error("create_artifact", msg)
        return _err_text(msg)

    write_frontmatter(target_file, full_meta, content)
    artifact_created(aid, atype, str(target_file))
    tool_ok("create_artifact", f"{aid} ({atype}) → {target_file.name}")
    return _text(f"✅ Artifact '{aid}' ({atype}) created at {target_file}")


async def _update_status(args: dict) -> list[TextContent]:
    aid        = args.get("id", "")
    new_status = args.get("new_status", "")
    note       = args.get("note", "")

    tool_call("update_status", {"id": aid, "new_status": new_status})

    if new_status not in VALID_STATUSES:
        msg = f"Invalid status '{new_status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"
        tool_error("update_status", msg)
        return _err_text(msg)

    idx   = build_index()
    entry = idx.get(aid)
    if not entry:
        msg = f"Artifact '{aid}' not found."
        tool_error("update_status", msg)
        return _err_text(msg)

    old_status = entry["meta"].get("status", "UNKNOWN")
    patch_frontmatter(entry["path"], {
        "status":         new_status,
        "last_updated":   datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "revision_count": entry["meta"].get("revision_count", 1) + 1,
    })

    log_dir = BLUEPRINT_ROOT / "dev_docs" / "quality" / "Review_Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    log_path = log_dir / f"STATUS-{aid}-{ts}.md"
    log_path.write_text(
        f"---\nartifact: {aid}\nold_status: {old_status}\nnew_status: {new_status}\ntimestamp: {ts}Z\n---\n\n{note}\n",
        encoding="utf-8",
    )
    status_change(aid, old_status, new_status)
    tool_ok("update_status", f"{aid}: {old_status} → {new_status}")
    return _text(f"✅ '{aid}' status updated: {old_status} → {new_status}")


async def _validate_all(_args: dict) -> list[TextContent]:
    tool_call("validate_all", {})
    report = validate_traceability()
    validate_result(len(report.errors))
    return _text(report.summary())


async def _run_self_critique(args: dict) -> list[TextContent]:
    artifact_id = args.get("artifact_id", "")
    tool_call("run_self_critique", {"artifact_id": artifact_id})

    idx   = build_index()
    entry = idx.get(artifact_id)
    if not entry:
        msg = f"Artifact '{artifact_id}' not found."
        tool_error("run_self_critique", msg)
        return _err_text(msg)

    critic_protocol = BLUEPRINT_ROOT / "protocols" / "review" / "R1_Agent_Self_Critic.md"
    protocol_text = (
        critic_protocol.read_text(encoding="utf-8")
        if critic_protocol.exists()
        else (
            "# R1 Self-Critic Protocol (default)\n"
            "Review the artifact below for:\n"
            "1. Logical gaps or contradictions\n"
            "2. Missing parent/child references\n"
            "3. Ambiguous or untestable requirements\n"
            "4. Hallucinated facts\n"
            "Output a structured list of issues found."
        )
    )

    artifact_text = entry["path"].read_text(encoding="utf-8")
    combined = (
        f"{protocol_text}\n\n"
        f"---\n\n## Artifact to critique: {artifact_id}\n\n"
        f"{artifact_text}"
    )

    log_dir  = BLUEPRINT_ROOT / "dev_docs" / "quality" / "Review_Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"CRITIC-{artifact_id}.md"
    log_path.write_text(
        f"---\nartifact: {artifact_id}\ntype: self_critique\nstatus: PENDING\n---\n\n"
        "<!-- Agent: append your critique below -->\n",
        encoding="utf-8",
    )
    tool_ok("run_self_critique", f"critique prompt ready for {artifact_id}")
    return _text(combined)


# ---------------------------------------------------------------------------
# Sprint & Execution Tools
# ---------------------------------------------------------------------------

async def _get_backlog(_args: dict) -> list[TextContent]:
    tool_call("get_backlog", {})
    backlog_dir = BLUEPRINT_ROOT / "execution" / "backlog"
    tasks = []
    if backlog_dir.exists():
        for f in backlog_dir.glob("TSK-*.md"):
            meta, _ = read_frontmatter(f)
            if meta:
                tasks.append(
                    f"- {meta.get('id', 'Unknown')}: {meta.get('title', 'No Title')} "
                    f"[Status: {meta.get('status', 'UNKNOWN')}]"
                )
    if not tasks:
        return _text("Backlog is empty.")
    return _text("Backlog Tasks:\n" + "\n".join(tasks))


async def _start_sprint(args: dict) -> list[TextContent]:
    task_ids = args.get("task_ids", [])
    goal = args.get("goal", "No goal specified.")
    tool_call("start_sprint", {"task_ids": task_ids, "goal": goal})
    
    idx = build_index()
    valid_tasks = []
    for tid in task_ids:
        entry = idx.get(tid)
        if not entry or entry["type"] != "Task":
            return _err_text(f"Task '{tid}' not found or is not a Task.")
        valid_tasks.append(entry)
        
    for entry in valid_tasks:
        patch_frontmatter(entry["path"], {
            "status": "IN_PROGRESS",
            "last_updated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        })
        status_change(entry["meta"].get("id"), entry["meta"].get("status"), "IN_PROGRESS")
        
    sprint_file = BLUEPRINT_ROOT / "execution" / "sprint_current.md"
    sprint_file.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [
        f"# Current Sprint",
        f"**Goal:** {goal}\n",
        f"## Tasks",
    ]
    for tid in task_ids:
        lines.append(f"- [ ] {tid}")
        
    sprint_file.write_text("\n".join(lines), encoding="utf-8")
    tool_ok("start_sprint", f"Started sprint with {len(task_ids)} tasks.")
    return _text(f"✅ Sprint started successfully with tasks: {', '.join(task_ids)}")


async def _log_session(args: dict) -> list[TextContent]:
    task_id = args.get("task_id", "General")
    action = args.get("action", "")
    result = args.get("result", "")
    tool_call("log_session", {"task_id": task_id})
    
    log_dir = BLUEPRINT_ROOT / "execution" / "session_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    log_file = log_dir / f"{today}.md"
    
    entry = f"\n### [{ts}Z] Task: {task_id}\n**Action:** {action}\n**Result:** {result}\n---\n"
    
    with log_file.open("a", encoding="utf-8") as f:
        f.write(entry)
        
    tool_ok("log_session", f"Logged session action for {task_id}")
    return _text(f"✅ Session log appended to {log_file.name}")


async def _harvest_knowledge(args: dict) -> list[TextContent]:
    topic = args.get("topic", "Unknown")
    description = args.get("description", "")
    code_snippet = args.get("code_snippet", "")
    tool_call("harvest_knowledge", {"topic": topic})
    
    k_dir = BLUEPRINT_ROOT / "inbound" / "Knowledge_Raw"
    k_dir.mkdir(parents=True, exist_ok=True)
    learnings_file = k_dir / "new_learnings.md"
    
    entry = f"\n## {topic}\n{description}\n"
    if code_snippet:
        entry += f"```\n{code_snippet}\n```\n"
    entry += "---\n"
    
    with learnings_file.open("a", encoding="utf-8") as f:
        f.write(entry)
        
    tool_ok("harvest_knowledge", f"Harvested: {topic}")
    return _text(f"✅ Knowledge harvested: {topic}")


async def _complete_task(args: dict) -> list[TextContent]:
    task_id = args.get("task_id", "")
    tool_call("complete_task", {"task_id": task_id})
    
    idx = build_index()
    entry = idx.get(task_id)
    if not entry or entry["type"] != "Task":
        return _err_text(f"Task '{task_id}' not found.")
        
    old_status = entry["meta"].get("status", "UNKNOWN")
    patch_frontmatter(entry["path"], {
        "status": "DONE",
        "last_updated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    })
    status_change(task_id, old_status, "DONE")
    
    sprint_file = BLUEPRINT_ROOT / "execution" / "sprint_current.md"
    if sprint_file.exists():
        content = sprint_file.read_text(encoding="utf-8")
        content = content.replace(f"- [ ] {task_id}", f"- [x] {task_id}")
        sprint_file.write_text(content, encoding="utf-8")
        
    tool_ok("complete_task", f"Completed {task_id}")
    return _text(f"✅ Task {task_id} marked as DONE.")


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "create_artifact":   _create_artifact,
    "update_status":     _update_status,
    "validate_all":      _validate_all,
    "run_self_critique": _run_self_critique,
    "get_backlog":       _get_backlog,
    "start_sprint":      _start_sprint,
    "log_session":       _log_session,
    "harvest_knowledge": _harvest_knowledge,
    "complete_task":     _complete_task,
}

_TOOL_SCHEMAS: list[Tool] = [
    Tool(
        name="create_artifact",
        description=(
            "Create a new blueprint artifact (Goal, Feature, Research, UseCase, Task) "
            "with full metadata validation and parent traceability check."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "type":      {"type": "string", "enum": sorted(VALID_TYPES)},
                "id":        {"type": "string", "description": "Unique ID, e.g. GL-001"},
                "parent_id": {"type": "string", "description": "ID of the parent artifact"},
                "content":   {"type": "string", "description": "Markdown body content"},
                "metadata":  {"type": "object", "description": "Additional YAML front-matter fields"},
            },
            "required": ["type", "id", "content"],
        },
    ),
    Tool(
        name="update_status",
        description="Update the status of an existing artifact and log the transition.",
        inputSchema={
            "type": "object",
            "properties": {
                "id":         {"type": "string"},
                "new_status": {"type": "string", "enum": sorted(VALID_STATUSES)},
                "note":       {"type": "string", "description": "Optional note about why status changed"},
            },
            "required": ["id", "new_status"],
        },
    ),
    Tool(
        name="validate_all",
        description="Scan all _blueprint/ artifacts and return a traceability validation report.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="run_self_critique",
        description=(
            "Load R1 self-critic protocol + the specified artifact "
            "and return a structured critique prompt for the LLM to process."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
            },
            "required": ["artifact_id"],
        },
    ),
    Tool(
        name="get_backlog",
        description="Scans the backlog and returns a list of Tasks with their statuses.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="start_sprint",
        description="Start a new sprint with selected tasks and a goal.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_ids": {"type": "array", "items": {"type": "string"}, "description": "List of Task IDs"},
                "goal":     {"type": "string", "description": "Goal of the sprint"},
            },
            "required": ["task_ids", "goal"],
        },
    ),
    Tool(
        name="log_session",
        description="Log an action and result to the daily session log.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Associated Task ID, or 'General'"},
                "action":  {"type": "string", "description": "What was done"},
                "result":  {"type": "string", "description": "Outcome or findings"},
            },
            "required": ["task_id", "action", "result"],
        },
    ),
    Tool(
        name="harvest_knowledge",
        description="Record newly discovered concepts, API caveats, or patterns.",
        inputSchema={
            "type": "object",
            "properties": {
                "topic":        {"type": "string", "description": "Topic name"},
                "description":  {"type": "string", "description": "Detailed explanation"},
                "code_snippet": {"type": "string", "description": "Optional code snippet demonstrating the concept"},
            },
            "required": ["topic", "description"],
        },
    ),
    Tool(
        name="complete_task",
        description="Mark a Task as DONE and check it off in the current sprint board.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to complete"},
            },
            "required": ["task_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_agent_tools(server: Server) -> None:

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return _TOOL_SCHEMAS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None = None) -> list[TextContent]:
        handler = _TOOL_HANDLERS.get(name)
        if not handler:
            return _err_text(f"Unknown tool '{name}'. Available: {', '.join(_TOOL_HANDLERS)}")
        return await handler(arguments or {})
