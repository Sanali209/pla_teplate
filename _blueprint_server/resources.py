"""
resources.py — MCP Resources for the Blueprint server.
Exposes live, read-only data about the _blueprint/ state to the LLM agent.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server import Server
from mcp.types import Resource, TextContent, ReadResourceResult, TextResourceContents

from config import BLUEPRINT_ROOT
from artifact_index import build_index, to_json
from fs_reader import read_frontmatter
from logger import resource_read


def register_resources(server: Server) -> None:
    """Register all blueprint:// resource URIs with the MCP server."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="blueprint://index",
                name="Artifact Index",
                description="Full artifact index (Goals→Features→UseCases→Tasks) as JSON",
                mimeType="application/json",
            ),
            Resource(
                uri="blueprint://pending",
                name="Pending Review Queue",
                description="All artifacts awaiting user approval or with unread feedback",
                mimeType="application/json",
            ),
            Resource(
                uri="blueprint://knowledge/brain",
                name="Knowledge Base",
                description="Aggregated Design Patterns and Anti-Patterns from the project brain",
                mimeType="text/plain",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:  # SDK expects a plain str return
        resource_read(str(uri))

        if str(uri) == "blueprint://index":
            idx  = build_index()
            data = to_json(idx)
            resource_read(f"blueprint://index  ({len(data)} artifacts)")
            return json.dumps(data, ensure_ascii=False, indent=2)

        if str(uri) == "blueprint://pending":
            idx = build_index()
            pending = [
                v for v in idx.values()
                if v["meta"].get("status") in ("REVIEW", "NEEDS_FIX")
            ]
            feedback_dir = BLUEPRINT_ROOT / "inbound" / "User_Feedback"
            feedbacks: list[dict] = []
            if feedback_dir.exists():
                for fb_file in sorted(feedback_dir.glob("FB-*.md")):
                    meta = read_frontmatter(fb_file)
                    if meta.get("read") is not True:
                        feedbacks.append({"feedback_file": str(fb_file), "meta": meta})
            payload = {
                "pending_artifacts": to_json(build_index_from(pending)),
                "unread_feedback":   feedbacks,
            }
            resource_read(
                f"blueprint://pending  ({len(pending)} pending, {len(feedbacks)} unread feedback)"
            )
            return json.dumps(payload, ensure_ascii=False, indent=2)

        if str(uri) == "blueprint://knowledge/brain":
            brain_dir = BLUEPRINT_ROOT / "dev_docs" / "brain"
            sections: list[str] = []
            for fname in ("Design_Patterns.md", "Anti_Patterns.md", "Terminology.md"):
                fpath = brain_dir / fname
                if fpath.exists():
                    sections.append(f"## {fname}\n\n{fpath.read_text(encoding='utf-8')}")
            return "\n\n---\n\n".join(sections) or "Knowledge base is empty."

        return f"Unknown resource URI: {uri}"


def build_index_from(entries: list[dict]) -> list[dict]:
    """Serialize a list of artifact entry dicts to JSON-safe list."""
    result = []
    for e in entries:
        result.append({
            "id":           e["meta"].get("id", ""),
            "type":         e.get("type", ""),
            "path":         str(e["path"]),
            "meta":         e["meta"],
            "body_snippet": e.get("body_snippet", ""),
        })
    return result
