# Anti-Patterns — Blueprint Knowledge Base

> Updated by: `H1_Pattern_Recognition.md`
> Read by: `blueprint://knowledge/brain` MCP Resource

This file captures known mistakes to avoid during the Blueprint workflow.
The MCP agent reads this before generating artifacts to prevent repeating past mistakes.

---

## AP-001: Creating Tasks Before Approving Use Cases
**Symptom:** Tasks are created but have dangling `parent_uc` references with `status: DRAFT`
**Cause:** Agent skipped the P3 approval gate
**Prevention:** Gate G1 in `Validation_Rules.md` — MCP server rejects TSK creation if parent UC is not APPROVED

## AP-002: Actors That Are Systems, Not Roles
**Symptom:** `actors: ["Database", "API"]` — these are system components, not actors
**Cause:** Agent confuses architectural layers with actors
**Prevention:** An actor is always a human role (`User`, `Admin`, `Guest`) or an external system (`ThirdPartyPaymentGateway`)

## AP-003: KPI Without Measurement Method
**Symptom:** `kpi: "Better user experience"` — not measurable
**Cause:** Vague goal writing
**Prevention:** Every KPI must include a measurable threshold: `kpi: "Page load < 2s for 95th percentile"`

---
<!-- Agent: add new anti-patterns discovered during NEEDS_FIX cycles below this line -->
