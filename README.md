# Blueprint Studio

> **AI-driven project planning system with a local MCP server and a PySide2 desktop GUI.**
> Design your application from a raw idea to atomic developer tasks — with full traceability from every task back to its originating business goal.

---

## What is this?

Blueprint Studio is a structured planning framework for software projects. It enforces a strict, phase-gated workflow where:

- An **LLM agent** generates and maintains planning documents (Goals, Features, Research, Use Cases, Tasks)
- A **local MCP server** acts as the agent's interface to the file system, enforcing traceability rules and providing protocol prompts
- A **PySide2 desktop GUI** gives the human user a clear view of system state, artifact navigation, and interactive critique tools

All three components share a single source of truth: the `_blueprint/` directory.

```
    │  P0: Ingestion
    ▼
Goals (GL-xxx) ──► P1.5: Sub-Goals if needed
    │  P1: Inception
    ▼
Features (FT-xxx) ──► [Research Spike (RS-xxx)] if needed
    │  P3: Analysis
    ▼
Use Cases (UC-xxx) ──► UML Diagrams (P3.5)
    │  P4: Dev Sync
    ▼
Tasks (TSK-xxx) + Fuzzing Vectors
    │  P5: Sprint Planning
    ▼
Sprint Board (IN_PROGRESS)
    │  E1: Sprint Execution
    ▼
DONE (Code, Tests, Session Logs) + Knowledge Harvest
    │
    ▼
[Bugs/Issues] ──► P0.5: Bug Triage (Back to Tasks or Use Cases)
```

Every artifact contains YAML metadata linking it to its parent, enabling full **reverse-path traceability** (any task → its use case → its feature → its goal).

---

## Repository Structure

```
📁 _blueprint/                  ← Single source of truth (all planning docs)
│   ├── protocols/
│   │   ├── meta/               ← Rules: Metadata schema, Naming, Validation, State machine
│   │   ├── generation/         ← Agent instructions: P0, P0.5, P1, P1.5, P2, P3, P3.5, P4, P5
│   │   ├── review/             ← Review protocols: R1 (self-critic), R2, R3, R4
│   │   ├── interactive/        ← Pause gates: S1 (approval), S2 (conflict), S3 (update)
│   │   ├── knowledge/          ← Harvesting: H1 (patterns), H2 (wiki)
│   │   └── templates/          ← Artifact templates: Goal, Feature, Research, UseCase, Task, UML
│   ├── dev_docs/
│   │   ├── brain/              ← Design_Patterns.md, Anti_Patterns.md, Terminology.md
│   │   ├── logic/              ← Features (FT-xxx) and Use Cases (UC-xxx)
│   │   ├── architecture/       ← UI_UX/ (SCR-xxx), UML models, Data_Schemas/
│   │   └── quality/Review_Logs/
│   ├── inbound/                ← Raw input: Briefings, MindMaps, Wireframes, Knowledge_Raw, Feedback, Bugs
│   └── execution/              ← roadmap.md, backlog/ (TSK-xxx), sessions/

📁 _blueprint_server/           ← MCP Server (agent interface)
│   ├── server.py               ← Entry point
│   ├── config.py               ← Path to _blueprint/ root
│   ├── fs_reader.py            ← YAML frontmatter reader/writer
│   ├── artifact_index.py       ← Live artifact index builder
│   ├── validate_traceability.py← Gate rule enforcer
│   ├── resources.py            ← MCP Resources (blueprint://index, pending, brain)
│   ├── prompts.py              ← MCP Prompts (P0–P5, E1, meta_rules, self_critic)
│   ├── agent_tools.py          ← MCP Tools (create_artifact, update_status, get_backlog, start_sprint...)
│   └── requirements.txt

📁 blueprint_gui/               ← PySide2 Desktop GUI (human interface)
│   ├── main.py                 ← Main window with 6 panels
│   ├── fs_reader.py            ← Local copy of frontmatter utility
│   └── requirements.txt

📄 Filling_Plan.md              ← Step-by-step workflow guide
📄 raw_data.md                  ← Original planning discussion (seed material)
```

---

## Quick Start

### 1. Install Dependencies

```bash
# MCP Server
pip install -r _blueprint_server/requirements.txt

# GUI
pip install -r blueprint_gui/requirements.txt

# Optional: PlantUML renderer (Java required)
# Download plantuml.jar from https://plantuml.com/download
# Add to PATH or create a plantuml wrapper script
```

### 2. Launch the GUI

```bash
python blueprint_gui/main.py
```

The GUI opens with 6 tabs:

| Tab | Purpose |
|---|---|
| 📋 **Entities** | Tables for Goals, Features, Research, Use Cases, Tasks — click any row to open in Viewer |
| 🔍 **Viewer** | Artifact tree + rendered Markdown + breadcrumb trace path (Task → UC → Feature → Goal) |
| 📝 **Critique** | APPROVE / REQUEST CHANGE / REJECT any artifact. Writes to `inbound/User_Feedback/` |
| 🗺 **UML** | Renders `.puml` files from `UML_Models/` using local PlantUML CLI. Zoom + export |
| 📥 **Inbound** | Create and edit raw input files in `_blueprint/inbound/`. Shows which protocol will process each folder |
| 🛣 **Roadmap** | Phase progress table with `approved / total` counts from live artifact statuses |

The GUI auto-refreshes whenever the MCP server writes new files (via `QFileSystemWatcher`).

### 3. Launch the MCP Server

```bash
cd _blueprint_server
python server.py
```

The server exposes:
- **3 Resources** — live JSON feeds: artifact index, pending review queue, knowledge base
- **Prompts** — protocol files mapped to named prompts (`p0_ingestion` through `e1_sprint_execution`, `meta_rules`, `self_critic`, `fix_protocol`)
- **13 Tools** — `create_artifact`, `update_status`, `validate_all`, `run_self_critique`, `get_backlog`, `start_sprint`, `log_session`, `harvest_knowledge`, `complete_task`, `search_artifacts`, `get_traceability_tree`, `update_brain_doc`, `validate_uml`

---

## Connecting to an LLM Agent

### Option A: Antigravity / Claude Desktop (any MCP-compatible client)

Add to your agent's MCP server config (usually `mcp_config.json` or `settings.json`):

```json
{
  "mcpServers": {
    "blueprint": {
      "command": "python",
      "args": ["d:/github/pla_teplate/_blueprint_server/server.py"],
      "cwd": "d:/github/pla_teplate/_blueprint_server"
    }
  }
}
```

### Option B: VS Code + Copilot (MCP extension)

1. Install the MCP extension for VS Code.
2. Open `.vscode/mcp.json` (create if missing):

```json
{
  "servers": {
    "blueprint": {
      "type": "stdio",
      "command": "python",
      "args": ["_blueprint_server/server.py"]
    }
  }
}
```

### Option C: Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python _blueprint_server/server.py
```

Opens a browser-based UI to manually call any Resource, Prompt, or Tool.

---

## How to Use with an Agent: Workflow Example

### Starting a new project

1. Drop your notes/brief into `_blueprint/inbound/Briefings/` (use the GUI Inbound Editor tab).
2. Tell the agent:
   > *"Load the blueprint meta rules and run P0 Ingestion on the files in inbound/Briefings/"*
3. Agent calls prompt `meta_rules` then `p0_ingestion` → produces a structured extraction summary.
4. Review the summary. If good: *"Continue with P1 Inception and create the Goal artifacts."*
5. Agent calls `create_artifact` for each Goal → they appear in the GUI Entities → Goals table.
6. Review Goals in GUI Critique panel → click **APPROVE**.
7. Agent detects approval (via `blueprint://pending`), continues to Features.
8. Repeat the cycle through P2 → P3 → P3.5 → P4.

### Critique Loop

1. Agent submits artifact for review: `update_status(UC-001, "REVIEW")`
2. GUI Entities table shows 🟡 REVIEW row.
3. Click the row → Viewer shows content + trace path.
4. Open Critique tab → write comment → click **REQUEST CHANGE**.
5. This writes `inbound/User_Feedback/FB-UC-001.md` and patches status to `NEEDS_FIX`.
6. Agent sees it in `blueprint://pending` → calls `run_self_critique(UC-001)` → applies fix → resubmits.

---

## Key Rules (Enforced by MCP Server)

| Rule | Effect |
|---|---|
| Task requires APPROVED parent UseCase | `create_artifact(Task)` rejected if parent UC is not APPROVED |
| Every artifact needs required YAML fields | `validate_all()` flags missing `id`, `title`, `status`, `parent_*` |
| Parent references must resolve | `validate_all()` flags dangling `parent_goal`, `parent_feat`, `parent_uc` |
| No duplicate IDs | `create_artifact` rejects if ID already exists |

---

## Customising the Protocols

All agent instructions are plain Markdown files in `_blueprint/protocols/`. Edit them directly — the MCP server re-reads them on every prompt call, so changes take effect immediately without restarting the server.

To add a new phase protocol:
1. Create `_blueprint/protocols/generation/P5_MyPhase.md`
2. Add it to `PROMPT_MAP` in `_blueprint_server/prompts.py`
3. Done — available to the agent as prompt `p5_myphase`

---

## Requirements

| Component | Requirement |
|---|---|
| Python | ≥ 3.10 |
| MCP SDK | `mcp >= 1.0` |
| GUI | `PySide2 >= 5.15`, `markdown >= 3.5`, `pyyaml >= 6.0` |
| UML render | Java + `plantuml` on PATH (optional) |
| Agent client | Any MCP-compatible client (Claude Desktop, Antigravity, VS Code Copilot) |