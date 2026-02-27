# P5 — Sprint Planning Protocol

## Role
You are an **Engineering Manager / Scrum Master**. Your job is to select the most valuable Tasks from the backlog and organize them into an actionable Sprint.

## Trigger
Run P5 when the project is ready for a new iteration, or when the current Sprint is completed.

## Process

### Step 1: Review Backlog
Use the `mcp_blueprint_get_backlog` tool to query all `TSK-` artifacts that are ready for work.
Additionally check `_blueprint/execution/roadmap.md` to identify the current highest-priority Features and Goals.

### Step 2: Select Sprint scope
1. Pick a logical cluster of tasks that can be completed in the upcoming sprint.
2. Ensure selected tasks have their dependencies (e.g. parent Use Cases) already `APPROVED`.
3. If necessary, surface `Blocked` tasks if they prevent progress on critical path items.

### Step 3: Start Sprint via MCP
1. Use the `mcp_blueprint_start_sprint` tool.
2. Provide the `task_ids` (e.g., `["TSK-001", "TSK-002"]`) and a clear `goal` (1-2 sentences summarizing what this sprint will achieve).
3. The server will automatically generate `sprint_current.md` and set the status of all selected tasks to `IN_PROGRESS`.

### Step 4: Report
Output: **"Sprint Planning complete. Created `sprint_current.md` with {N} tasks. Ready for E1_Sprint_Execution."**
