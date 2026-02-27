# Validation Rules — Blueprint Protocol

## Purpose
This file defines the gate rules and validation logic used by both
the **MCP Server** (`validate_traceability.py`) and the **GUI** (Critique Panel).
Any agent action that violates these rules will be rejected with an error.

---

## Gate Rules (Hard Blocks)

| Rule | Condition | Error Message |
|---|---|---|
| **G1: Task Gate** | Task cannot be created if `parent_uc` status ≠ `APPROVED` | "Gate blocked: UseCase must be APPROVED before Tasks are created." |
| **G2: Analysis Gate** | Use Case cannot be created if parent Feature has `research_required: true` but no linked RS with `verdict: SUCCESS` | "Gate blocked: Feature requires a successful Research Spike first." |
| **G3: Orphan Check** | Every `parent_goal`, `parent_feat`, `parent_uc`, `origin` must resolve to an existing artifact ID | "Orphan: parent reference '{id}' not found in artifact index." |
| **G4: Duplicate ID** | No two artifacts may share the same ID | "Duplicate: ID '{id}' already exists." |
| **G5: Field Completeness** | Required fields (per Metadata_Schema.md) must all be present and non-empty | "Missing required field '{field}' for artifact type '{type}'." |

---

## Soft Warnings (Agent should flag but not block)

| Code | Situation |
|---|---|
| **W1** | Feature has no linked Use Cases after 24h |
| **W2** | Task status is DRAFT for more than 7 days |
| **W3** | Artifact with `status: NEEDS_FIX` has no linked `FB-*.md` feedback file |

---

## Reverse-Path Traversal Rules

To reconstruct the full trace from any artifact back to its Goal:

1. Read `parent_uc` → `UC-xxx`.
2. Read `parent_feat` on the UseCase → `FT-xxx`.
3. Read `parent_goal` on the Feature → `GL-xxx`.
4. If any link is broken, flag as **G3: Orphan**.

The MCP `validate_all()` tool runs this check on every artifact in the index.

---

## Status Transition Rules

```
DRAFT ──► REVIEW ──► APPROVED
                └──► NEEDS_FIX ──► REVIEW (cycle)
APPROVED ──► DONE
APPROVED ──► ARCHIVED
```

**Forbidden transitions:**
- `APPROVED → DRAFT` (must go through NEEDS_FIX cycle)
- `DONE → any` (terminal state; create a new version instead)
