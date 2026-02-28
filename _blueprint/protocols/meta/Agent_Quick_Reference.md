# Agent Quick Reference — Blueprint Protocol

> **Load this file at the start of every session.** It is the single cheat sheet
> for all IDs, statuses, tool signatures, and anti-patterns.

---

## 1. ID Prefixes & Storage Directories

| Type | ID Prefix | ID Example | Directory |
|---|---|---|---|
| Goal | `GL-` | `GL-001` | `dev_docs/brain/` |
| Feature | `FT-` | `FT-001` | `dev_docs/logic/` |
| Research | `RS-` | `RS-001` | `dev_docs/brain/R_D_Archive/` |
| UseCase | `UC-` | `UC-001` | `dev_docs/logic/` |
| Task | `TSK-` | `TSK-001` | `execution/backlog/` |
| UML Draft | `UML-` | `UML-001` | `dev_docs/architecture/UML_Models/Drafts/` |
| Feedback | `FB-` | `FB-GL-001` | `inbound/User_Feedback/` |

> ⚠️ **ALWAYS call `get_next_id(type)` before `create_artifact`** — never guess the ID.

---

## 2. Status Lifecycle

```
DRAFT ──► REVIEW ──► APPROVED ──► DONE
              │                └──► ARCHIVED
              └──► NEEDS_FIX ──► REVIEW (cycle)
              └──► REJECTED  ──► REVIEW (fix) | ARCHIVED (empty reason)
```

**Forbidden transitions (server will block these):**
- `APPROVED → DRAFT` or `APPROVED → REVIEW` — use NEEDS_FIX first
- `DONE → anything` except ARCHIVED — DONE is terminal

---

## 3. Gate Rules (Hard Blocks)

| Gate | Rule |
|---|---|
| **G1** | Task cannot exist if `parent_uc` status ≠ APPROVED |
| **G2** | UseCase cannot exist if parent Feature has `research_required: true` without SUCCESS RS |
| **G3** | Every `parent_*` field must resolve to an existing artifact ID |
| **G4** | File name must match declared `id` field |
| **G5** | All required YAML fields must be non-empty |
| **G6** | Forbidden status transitions are blocked by `update_status` |

---

## 4. Most-Used Tool Signatures

```python
# Get the next safe ID — call BEFORE create_artifact
mcp_blueprint_get_next_id(type="Goal")
# → next_id: GL-003

# Create an artifact
mcp_blueprint_create_artifact(
    type="Goal",
    id="GL-003",
    content="## Description\n...",
    metadata={"title": "...", "status": "DRAFT", "owner": "...", "kpi": "..."},
)

# Update status (forbidden transitions will error)
mcp_blueprint_update_status(id="GL-001", new_status="REVIEW", note="Ready for review")

# Run full validation
mcp_blueprint_validate_all()

# Read rejection reason when artifact is NEEDS_FIX / REJECTED
mcp_blueprint_read_rejection(artifact_id="UC-003")

# Search RAG before writing code or making decisions
mcp_blueprint_search_rag(query="how to implement JWT auth")

# Log session action
mcp_blueprint_log_session(task_id="TSK-005", action="Implemented X", result="Tests pass")
```

---

## 5. Protocol Quick Map

| Phase | Protocol | Trigger |
|---|---|---|
| P0 | Ingest raw docs → structured summary | New files in `inbound/` |
| P1 | Create Goals + Features + Roadmap | After P0 approval |
| P2 | Research Spike → verdict | Feature with `research_required: true` |
| P3 | Create Use Cases from Features | Features APPROVED |
| P4 | Create Tasks from Use Cases | Use Cases APPROVED |
| P5 | Sprint Planning | Backlog populated |
| E1 | Sprint Execution | Sprint started |
| R1 | Self-Critique | Before any REVIEW submission |
| R2 | Apply user critique | After NEEDS_FIX or REJECTED |
| S4 | Rejection handler | When reading NEEDS_FIX/REJECTED |

---

## 6. Anti-Patterns Hall of Shame

| ❌ Anti-Pattern | ✅ Correct |
|---|---|
| Using `RSH-001` for Research | Use `RS-001` |
| Guessing the next ID | Call `get_next_id(type)` first |
| Skipping R1 self-critique before REVIEW | Always run R1 |
| Setting status to APPROVED directly | Wait for human to approve via GUI |
| Creating Task without APPROVED UseCase parent | Gate G1 will block it |
| Silent rejection handling | Always call `read_rejection` and follow S4 |
