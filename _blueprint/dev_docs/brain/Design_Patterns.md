# Design Patterns — Blueprint Knowledge Base

> Updated by: `H1_Pattern_Recognition.md`
> Read by: `blueprint://knowledge/brain` MCP Resource

This file accumulates proven design patterns discovered during project execution.
The MCP server serves this file to the LLM agent as background context to prevent reinventing the wheel.

---

## DP-001: Approval-Gated Artifact Creation
**Context:** When the agent wants to generate child artifacts (Features, Use Cases, Tasks)
**Solution:** Always check that the parent artifact is `APPROVED` before creating children. Use `validate_all()` to confirm gate state.
**Evidence:** Defined in `Validation_Rules.md` (G1–G3)

## DP-002: Hypothesis-First Research
**Context:** When a Feature requires a technology choice or architectural decision
**Solution:** Write a falsifiable hypothesis first (`RS-xxx`), then conduct the minimum experiment. Never commit to a design without a `verdict: SUCCESS`.
**Evidence:** `P2_Research.md`

## DP-003: Failure-Points-to-Fuzzing Pipeline
**Context:** When decomposing Use Cases into Tasks
**Solution:** Every Failure Point in a UC maps to at least one Fuzzing Vector in a TSK. This ensures QA is planned at design time, not as an afterthought.
**Evidence:** `P4_Dev_Sync.md` + `Task_Tpl.md`

---
<!-- Agent: add new patterns discovered during project execution below this line -->
