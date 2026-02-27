# 🧠 The Blueprint (AI Agent Workspace)

**[CRITICAL INSTRUCTION FOR ALL AI AGENTS]**
If you are reading this file, you have entered the **Blueprint** workspace (`_blueprint/`). This is NOT the source code directory. **This is the system's brain.**

The Blueprint is a highly structured, strict, pipeline-driven architecture framework. It enforces a separation between *thinking* (planning, designing, validating) and *doing* (writing application code).

Your primary tool here is **NOT** editing files manually. Your primary tools are the **MCP Blueprint Server Tools** (`create_artifact`, `update_status`, `validate_all`, `run_self_critique`, etc.).

---

## 🏗️ Directory Structure

The Blueprint is divided into strict chronological and functional folders. Do not place files where they don't belong.

### 1. `inbound/` (The Intake)
- What it is: The entry point for all raw, unstructured concepts.
- **`Briefings/`**: Meeting notes, chat logs, user briefs.
- **`Knowledge_Raw/`**: API documentation, tutorials, external references.
- **`MindMaps/`**: Visual diagrams, Miro exports.
- **`Wireframes/`**: Screenshots and design mockups (.png, .jpg).
- **`User_Feedback/`**: Critiques and corrections provided by human user.
- **`Issues_and_Bugs/`**: Bug reports, QA tickets, or Sentry logs.
- *Agent Action:* Run `P0_Ingestion`, `P0_5_Bug_Triage`, or `P2_5_UI_Architecture` depending on the inbound type.

### 2. `dev_docs/` (The Architects' Room)
- What it is: Where abstract concepts turn into technical reality.
- **`brain/`**: The permanent memory. Contains Goals (`GL-xxx`), `Terminology.md`, `Design_Patterns.md`, and `Anti_Patterns.md`.
- **`logic/`**: The behavioral design. Contains Features (`FT-xxx`) and Use Cases (`UC-xxx`).
- **`architecture/`**: Visual and structural design.
  - `UI_UX/` (Screens `SCR-xxx` derived from wireframes)
  - `UML_Models/` (PlantUML Drafts/ and Approved/)
  - `Data_Schemas/` (API/DB structures)
- **`quality/`**: The validation layer. Contains `Review_Logs/`.

### 3. `execution/` (The Factory Floor)
- What it is: Where architectural designs become actionable chunks.
- **`roadmap.md`**: The high-level timeline of Features and Goals.
- **`backlog/`**: Atomic developer tasks (`TSK-xxx.md`) generated from Use Cases. Ready to be built.
- **`sprint_current.md`**: The active Kanban board. Tasks currently in progress.
- **`session_logs/`**: Daily logs of what you (the Agent) did, bugs found, and code written.

### 4. `protocols/` (The Law)
- What it is: The instruction manuals for YOU. Never guess what to do; read the protocol.
- **`generation/`**: Protocols for creating new artifacts (P0-P5, P0.5 Bug Triage).
- **`execution/`**: Protocols for doing the work (E1).
- **`review/`**: Protocols for finding errors (R1-R4).
- **`interactive/`**: Protocols for talking to the human (S1-S3).
- **`knowledge/`**: Protocols for updating the brain (H1-H2).
- **`templates/`**: The strict Markdown YAML-frontmatter structures you MUST use when generating artifacts.
- **`meta/`**: Rules on traceability, state machines, and naming conventions.

### 5. `skills/` & `.vectordb/` (Agentic RAG)
- What it is: The passive knowledge base for context injection.
- **`skills/`**: Markdown files containing reusable code snippets, framework best practices, and setup guides.
- **`.vectordb/`**: Local ChromaDB instance. The `mcp_blueprint_index_knowledge` tool vectorize files from `skills/`, `session_logs/`, `brain/`, and `Knowledge_Raw/` so they can be retrieved via semantic search during task generation.

---

## 🚦 Core Philosophy & Rules

### Rule 1: The Pipeline is Sacred (State Machine)
Artifacts move in one direction:
`DRAFT` → (Agent Critique) → `REVIEW` → (Human Approval) → `APPROVED`.
**NEVER** generate a downstream artifact if the parent is not `APPROVED`.
*Example:* You cannot generate a Use Case (`UC-xxx`) if its parent Feature (`FT-xxx`) is not `APPROVED`.

### Rule 2: Complete Traceability
Every artifact must point back to why it exists.
A Task points to a Use Case (`parent_uc`). A Use Case points to a Feature (`parent_feat`). A Feature points to a Goal (`parent_goal`).
If a file has no parent, it is an orphan and will be rejected by the validation tools.

### Rule 3: Do Not Edit Files Manually (Use Tools)
To modify the status of an artifact, do **not** use `replace_file_content`.
Call the MCP tool `mcp_blueprint_update_status(id="FT-001", new_status="APPROVED")`. The server will safely update the frontmatter and log the transition.
To create a goal, use `mcp_blueprint_create_artifact()`. 
**NEVER** use `ls` or `cat` to search for files, use `mcp_blueprint_search_artifacts()`.
**NEVER** grep for parent relationships, use `mcp_blueprint_get_traceability_tree()`.
**NEVER** append strings to `brain/` docs, use `mcp_blueprint_update_brain_doc()`.

### Rule 4: Harvest Knowledge
When writing code (Phase E1), if you encounter a new error, a weird API quirk, or invent a good architectural pattern, immediately use `mcp_blueprint_harvest_knowledge()` to save it. Do not let your context window expire and lose that knowledge.

---

## 🛠️ Typical Agent Workflows

*   **You are asked to analyze an idea:** Read `protocols/generation/P1_Inception.md`. Use `create_artifact` to make Goals.
*   **You are asked to write code (Sprint):** Read `protocols/execution/E1_Sprint_Execution.md`. Use `mcp_blueprint_log_session()` to document your progress.
*   **You are asked to check your own work:** Read `protocols/review/R1_Agent_Self_Critic.md`. Use `mcp_blueprint_run_self_critique(artifact_id)`.
*   **You are asked to plan a sprint:** Use `mcp_blueprint_get_backlog()`, pick the best items, then use `mcp_blueprint_start_sprint()`.
