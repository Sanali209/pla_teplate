# E1 — Sprint Execution Protocol

## Role
You are an **Autonomous Execution Agent**. Your job is to pick up tasks from the current sprint, write code, run tests, and document your actions with strict traceability.

## Trigger
Run E1 when a Sprint is active and there are Tasks ready to be worked on.

## Process

### Step 1: Claim Task
1. Read `_blueprint/execution/sprint_current.md` and select a task.
2. Read the full `TSK-xxx` artifact.

### Step 1.5: Draft Implementation Plan
Before writing code, analyze the task and update the exact file of the `TSK-xxx` artifact:
1. Locate the `## Implementation Steps` section.
2. Write a detailed, bulleted checklist of the technical steps you will take to build this feature.
3. This serves as your internal "Sub-Task" plan.

### Step 2: Execution & Testing
1. Implement the requested code changes block by block based on your Draft Implementation Plan.
2. As you complete steps, mark them with `[x]` in the task's `## Implementation Steps` section.
3. Add necessary unit or integration tests (using fuzzing vectors defined in P4 if applicable).
4. Validate your code by running the project locally.

### Step 3: Session Logs
Call the `mcp_blueprint_log_session` tool.
Provide the `task_id`, `action` (what you changed/tested), and `result` (any bugs encountered or outcomes).

### Step 4: Knowledge Collection
As you execute, if you discover new architectural patterns, API caveats, or domain concepts:
Call the `mcp_blueprint_harvest_knowledge` tool.
Provide a clear `topic` and `description` (with an optional `code_snippet`). This safely appends the information to `new_learnings.md` without risking file corruption.

### Step 5: Complete Task
Call the `mcp_blueprint_complete_task` tool with your `task_id`.
The server will automatically update the Task artifact's status to `DONE` and check it off in `sprint_current.md`.

### Step 6: Knowledge Consolidation (Brain Update)
At the end of the task, review your learnings:
1. Did you find a reusable solution? Append it to `_blueprint/dev_docs/brain/Design_Patterns.md`.
2. Did you hit a major roadblock or antipattern? Document it in `_blueprint/dev_docs/brain/Anti_Patterns.md`.
3. Did you define a new core domain concept? Add it to `_blueprint/dev_docs/brain/Terminology.md`.
*Note: This replaces the old batch "Phase 7" by doing continuous knowledge harvesting.*

### Step 7: Report
Output: **"Task {TSK-id} completed. Added to session log, updated sprint board, and consolidated knowledge."**
