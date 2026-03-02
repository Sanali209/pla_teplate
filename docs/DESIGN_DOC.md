# [DESIGN_DOC]
Context:
- Problem: Need to integrate dependency analysis into pipelines to improve roadmap and sprint planning.
- Constraints: Must follow existing Metadata Schema and Validation Rules.
- Non-goals: Changing the fundamental traceability mechanism (unless necessary).

Architecture:
- Components:
  - Metadata Schema: YAML front-matter in artifacts.
  - Validation Rules: `validate_traceability.py` in `_blueprint_server`.
  - MCP Tools: `agent_tools.py` in `_blueprint_server`.
  - Templates: Folder `_blueprint/protocols/templates`.
- Data flow: Artifacts -> Metadata -> MCP Validation -> Roadmap/Sprint.
- External dependencies: ChromaDB (for RAG).

Key Decisions:
- [D1] Create `dev_log` and `journal` – Rationale: user global rules.
- [D2] Add `dependencies` field to `FT` and `TSK` – Rationale: Enable cross-feature and cross-task dependency tracking beyond simple parent-child relationships.

Interfaces:
- Metadata Schema:
  - Responsibility: Defining the structure of artifacts.
  - Public API: YAML fields including `dependencies`.
- MCP `validate_all`:
  - Responsibility: Enforce Gate Rules, including the new Dependency Gate (G8).
- MCP `analyze_dependencies`:
  - Responsibility: Return a JSON dependency graph of all artifacts.
- Dependency Analyzer (Script):
  - Responsibility: Standalone CLI to Scan `_blueprint/` for dependency links.

Assumptions & TODOs:
- Assumptions: Pipelines are represented by the flow GL -> FT -> UC -> TSK.
- Open questions: Should we automate the "critical path" detection?
- TODOs (with priority):
  - [P0] Implement `dependency_analyzer.py` logic.
  - [P0] Update `validate_traceability.py` with Horizontal Dependency Check (G8).
  - [P1] Add `analyze_dependencies` tool to `agent_tools.py`.
  - [P1] Create `Roadmap_Tpl.md` for visualizing the feature sequence.
  - [P1] Create `Sprint_Tpl.md` for grouping tasks into 2-week blocks based on dependencies.
[/DESIGN_DOC]
