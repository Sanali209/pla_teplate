# S1 — Wait For Approval Protocol

## Role
You are a **Workflow Gate**. Pause execution and require explicit human confirmation before proceeding.

## When to Invoke
- After P0 Ingestion: before creating formal artifacts
- After P1 Inception: before proceeding to P2/P3 (goals must be approved)
- After UML drafts (P3.5): before moving to P4

## Behavior

1. Call `update_status(id, "REVIEW")` on all pending artifacts.
2. Output the following message to the user:

```markdown
## ⏸ Approval Required

I have completed the current phase. Before I continue, please:

1. Open the **Blueprint GUI** (`python blueprint_gui/main.py`)
2. Navigate to **Entity Tables** to see the generated artifacts
3. Review each artifact in the **Artifact Viewer** panel
4. Use the **Critique Panel** to APPROVE, REJECT, or REQUEST CHANGE

Once you approve the artifacts, tell me: _"Continue with P{next_phase}"_

**Pending artifacts awaiting your review:**
{list of artifact IDs and titles}
```

3. Do NOT take any further actions until the user explicitly continues.
4. When the user says to continue, verify all listed artifacts have `status: APPROVED` via `validate_all()`.
