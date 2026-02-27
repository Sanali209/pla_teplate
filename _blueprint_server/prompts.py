"""
prompts.py — MCP Prompts for the Blueprint server.
Reads protocol .md files from _blueprint/protocols/ and registers them as named MCP Prompts.
"""

from __future__ import annotations

from mcp.server import Server
from mcp.types import Prompt, PromptMessage, TextContent

from config import BLUEPRINT_ROOT
from logger import prompt_load

PROTOCOLS_DIR = BLUEPRINT_ROOT / "protocols"

# Name → relative path inside protocols/
PROMPT_MAP: dict[str, str] = {
    "p0_ingestion":        BLUEPRINT_ROOT / "protocols" / "generation" / "P0_Ingestion.md",
    "p0_5_bug_triage":     BLUEPRINT_ROOT / "protocols" / "generation" / "P0_5_Bug_Triage.md",
    "p1_inception":        BLUEPRINT_ROOT / "protocols" / "generation" / "P1_Inception.md",
    "p1_5_goal_decomp":    BLUEPRINT_ROOT / "protocols" / "generation" / "P1_5_Goal_Decomposition.md",
    "p2_research":         BLUEPRINT_ROOT / "protocols" / "generation" / "P2_Research.md",
    "p2_5_ui_architecture": BLUEPRINT_ROOT / "protocols" / "generation" / "P2_5_UI_Architecture.md",
    "p3_analysis":         BLUEPRINT_ROOT / "protocols" / "generation" / "P3_Analysis.md",
    "p4_dev_sync":         BLUEPRINT_ROOT / "protocols" / "generation" / "P4_Dev_Sync.md",
    "p5_sprint_planning":  BLUEPRINT_ROOT / "protocols" / "generation" / "P5_Sprint_Planning.md",
    "e1_sprint_execution": BLUEPRINT_ROOT / "protocols" / "execution" / "E1_Sprint_Execution.md",
    "meta_rules":          BLUEPRINT_ROOT / "protocols" / "meta" / "Metadata_Schema.md",
    "self_critic":         BLUEPRINT_ROOT / "protocols" / "review" / "R1_Agent_Self_Critic.md",
    "fix_protocol":        BLUEPRINT_ROOT / "protocols" / "review" / "R3_Fix_and_Refactor.md",
}

DESCRIPTIONS: dict[str, str] = {
    "p0_ingestion": "Convert raw inbound material into structured blueprint artifacts",
    "p0_5_bug_triage": "Triage a bug report into a structured artifact",
    "p1_inception": "Transform a project idea into strategic Goals and Roadmap",
    "p1_5_goal_decomp": "Decompose a high-level goal into actionable sub-goals",
    "p2_research":  "Plan and conduct R&D spikes to eliminate uncertainty",
    "p2_5_ui_architecture": "Design the UI architecture for a feature",
    "p3_analysis":  "Decompose a Feature into Use Cases and User Flows",
    "p4_dev_sync":  "Generate atomic Tasks and Fuzzing specs from approved Use Cases",
    "meta_rules":   "Metadata schema and file naming rules for all artifacts",
    "self_critic":  "Review an artifact for logical gaps and hallucinations",
    "fix_protocol": "Apply user critique and re-generate a fixed version of an artifact",
}


def _load_protocol(rel_path: str) -> str:
    fpath = PROTOCOLS_DIR / rel_path
    if fpath.exists():
        return fpath.read_text(encoding="utf-8")
    return f"# Protocol file not found\nExpected: {fpath}\nCreate this file to activate the protocol."


def register_prompts(server: Server) -> None:
    """Register all blueprint protocol files as MCP Prompts."""

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name=name,
                description=DESCRIPTIONS.get(name, ""),
                arguments=[],
            )
            for name in PROMPT_MAP
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None = None) -> list[PromptMessage]:
        # `name` may come as a positional arg from SDK dispatcher
        rel_path = PROMPT_MAP.get(str(name))
        if not rel_path:
            content = f"Unknown prompt: {name}. Available: {', '.join(PROMPT_MAP)}"
        else:
            prompt_load(str(name), rel_path)
            content = _load_protocol(rel_path)
        return [
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ]
