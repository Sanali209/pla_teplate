# Terminology — Blueprint Knowledge Base

> Updated by: `H2_Wiki_Update.md`
> Read by: `blueprint://knowledge/brain` MCP Resource

Core glossary of concepts used across all Blueprint artifacts and protocols.

---

### Goal (GL)
**Type:** Entity
**Definition:** A high-level business objective the project aims to achieve, defined with a measurable KPI.
**First used in:** `Metadata_Schema.md`

### Feature (FT)
**Type:** Entity
**Definition:** A functional capability of the system that serves one or more Goals. Has a scope boundary (In Scope / Out of Scope).
**First used in:** `Metadata_Schema.md`

### Research Spike (RS)
**Type:** Entity
**Definition:** A time-boxed investigation to eliminate a technical uncertainty blocking a Feature's design.
**First used in:** `P2_Research.md`

### Use Case (UC)
**Type:** Entity
**Definition:** A concrete interaction scenario between an actor and the system, with a defined Happy Path, alternative flows, and failure points.
**First used in:** `Metadata_Schema.md`

### Task (TSK)
**Type:** Entity
**Definition:** An atomic, single-layer work item assigned to one developer. Directly traceable to a Use Case.
**First used in:** `Metadata_Schema.md`

### Reverse Path (Traceability)
**Type:** Process
**Definition:** The ability to trace any artifact upward through its parent chain to the originating Goal. Enforced by `validate_traceability.py`.
**First used in:** `Validation_Rules.md`

### Gate
**Type:** Process
**Definition:** A validation checkpoint that blocks creation of child artifacts until parent artifacts reach `APPROVED` status.
**First used in:** `Validation_Rules.md`

### Fuzzing Vector
**Type:** Process
**Definition:** A specific bad input or edge case derived from a Use Case Failure Point, used to define QA test cases.
**First used in:** `Task_Tpl.md`

### MCP Server
**Type:** Technology
**Definition:** The Model Context Protocol server that mediates all LLM agent actions on the `_blueprint/` file system.
**First used in:** `implementation_plan.md`

### Blueprint GUI
**Type:** Technology
**Definition:** The PySide2 desktop application providing the human user with artifact navigation, viewing, and critique capabilities.
**First used in:** `implementation_plan.md`

---
<!-- Agent: add new terms discovered during project execution below this line -->
