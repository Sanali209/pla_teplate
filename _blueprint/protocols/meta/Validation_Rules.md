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
| **G2: Analysis Gate** | UseCase cannot be created if parent Feature has `research_required: true` but no linked RS with `verdict: SUCCESS` or `PENDING` | "Gate blocked: Feature requires a successful Research Spike first." |
| **G3: Orphan Check** | Every `parent_goal`, `parent_feat`, `parent_uc`, `origin` must resolve to an existing artifact ID | "Orphan: parent reference '{id}' not found in artifact index." |
| **G4: Filename Match** | File name must match the declared `id` field | "Duplicate or mismatch: file '{name}' declares id '{id}'." |
| **G5: Field Completeness** | Required fields (per Metadata_Schema.md) must all be present and non-empty | "Missing required field '{field}' for artifact type '{type}'." |
| **G6: Forbidden Transition** | `APPROVED → DRAFT/REVIEW` is forbidden; `DONE → any` except ARCHIVED | "Forbidden transition: cannot move from {from} → {to}." |
| **G7: ID Monotonicity** | IDs must be zero-padded sequential integers; no gaps allowed | "Non-sequential ID detected: expected {expected}, got {actual}." |

---

## Soft Warnings (Agent should flag but not block)

| Code | Situation |
|---|---|
| **W1** | Feature has no linked Use Cases after 24h |
| **W2** | Task status is DRAFT for more than 7 days |
| **W3** | Artifact with `status: NEEDS_FIX` or `REJECTED` has no linked `FB-*.md` feedback file |
| **W4** | UseCase has `status: APPROVED` but zero linked Tasks |

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
DRAFT ──► REVIEW ──► APPROVED ──► DONE (terminal)
              │                └──► ARCHIVED
              ├──► NEEDS_FIX ──► REVIEW (cycle)
              └──► REJECTED  ──► REVIEW (fixed) | ARCHIVED (no reason)
```

**Forbidden transitions (server enforces G6):**
- `APPROVED → DRAFT` — must go through NEEDS_FIX cycle
- `APPROVED → REVIEW` — must go through NEEDS_FIX cycle
- `DONE → DRAFT/REVIEW/APPROVED/...` — DONE is terminal; create a new artifact version instead
