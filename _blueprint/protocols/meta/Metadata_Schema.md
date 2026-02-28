# Metadata Schema — Blueprint Protocol

## Purpose
Every artifact file in `_blueprint/` MUST begin with a YAML front-matter block.
This is the contract that enables the **reverse-path (Traceability)** and the **MCP server validation**.

---

## Required Fields by Artifact Type

### Goal (`GL-xxx`)
```yaml
---
id: GL-001                    # Unique ID. Prefix: GL-
title: "Short goal name"
status: DRAFT                 # DRAFT | REVIEW | APPROVED | DONE | ARCHIVED
owner: "Name or role"
kpi: "Measurable success metric"
created_at: 2026-01-01T00:00:00Z
revision_count: 1
---
```

### Feature (`FT-xxx`)
```yaml
---
id: FT-001
title: "Feature name"
status: DRAFT
priority: HIGH                # HIGH | MEDIUM | LOW
parent_goal: GL-001           # REQUIRED — reverse path to Goal
research_required: false      # true = R&D spike needed before P3
created_at: 2026-01-01T00:00:00Z
revision_count: 1
---
```

### Research Spike (`RS-xxx`)
```yaml
---
id: RS-001
parent_goal: GL-001           # REQUIRED
hypothesis: "If we do X, then Y"
verdict: PENDING              # PENDING | SUCCESS | FAILED
created_at: 2026-01-01T00:00:00Z
revision_count: 1
---
```

### Use Case (`UC-xxx`)
```yaml
---
id: UC-001
title: "Scenario name"
status: DRAFT
parent_feat: FT-001           # REQUIRED — reverse path to Feature
actors: ["User", "System"]
research_ref: RS-001          # Optional reference to R&D verdict
created_at: 2026-01-01T00:00:00Z
revision_count: 1
---
```

### Task (`TSK-xxx`)
```yaml
---
id: TSK-001
title: "Atomic work item"
status: DRAFT
parent_uc: UC-001             # REQUIRED — reverse path to Use Case
assignee: ""
created_at: 2026-01-01T00:00:00Z
revision_count: 1
---
```

---

## Rules enforced by MCP Server (`validate_traceability.py`)

1. Every artifact MUST have an `id` with the correct prefix for its folder.
   - **Research MUST use `RS-`**. (NEVER use `RSH-`).
   - **Goals MUST use `GL-`**.
   - **Features MUST use `FT-`**.
   - **Tasks MUST use `TSK-`**.
   - **UseCases MUST use `UC-`**.
2. Every `parent_*` field MUST resolve to an existing artifact ID.
3. A `Task` CANNOT exist if its `parent_uc` does not have `status: APPROVED`.
4. `revision_count` MUST be incremented on every `update_status` call.

---

## Status Values

| Status | Meaning |
|---|---|
| `DRAFT` | Created by agent, not yet reviewed |
| `REVIEW` | Submitted for human review |
| `APPROVED` | Human approved — unlocks child artifacts |
| `NEEDS_FIX` | Human rejected with feedback |
| `BLOCKED` | Cannot proceed due to unresolved dependency |
| `DONE` | Implementation complete |
| `ARCHIVED` | Deprecated, kept for history |

---

## Agent Behavior Rules (Agentic RAG & Skills)

1. **Exploring References:** If a `search_rag` query returns a snippet that contains a link to another markdown file (e.g., `[references/async-patterns.md](...)`), you **MAY** use the `view_file` tool to read the full contents of that linked file if you need more context.
2. **Executing Scripts:** If a Skill document mentions executable scripts (e.g., `.py` scripts in a `scripts/` subfolder), you **MAY** execute them directly using the `run_command` tool (e.g., `python _blueprint/skills/senior-architect/scripts/dependency_analyzer.py --help`). Always run with `--help` first to understand the arguments.
