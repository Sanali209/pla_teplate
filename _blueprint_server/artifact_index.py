"""
artifact_index.py — Builds and queries the full artifact index from the _blueprint/ file system.
Handles: Goals (GL), Features (FT), Research (RS), Use Cases (UC), Tasks (TSK).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config import BLUEPRINT_ROOT
from fs_reader import read_frontmatter, read_body


# ---------------------------------------------------------------------------
# Artifact type → directory mapping
# ---------------------------------------------------------------------------

ARTIFACT_DIRS: dict[str, Path] = {
    "Goal":     BLUEPRINT_ROOT / "dev_docs" / "brain",
    "Feature":  BLUEPRINT_ROOT / "dev_docs" / "logic",
    "Research": BLUEPRINT_ROOT / "dev_docs" / "brain" / "R_D_Archive",
    "UseCase":  BLUEPRINT_ROOT / "dev_docs" / "logic",
    "Task":     BLUEPRINT_ROOT / "execution" / "backlog",
}

ID_PREFIXES: dict[str, str] = {
    "GL":  "Goal",
    "FT":  "Feature",
    "RS":  "Research",
    "UC":  "UseCase",
    "TSK": "Task",
}


def _type_from_id(artifact_id: str) -> str | None:
    for prefix, atype in ID_PREFIXES.items():
        if artifact_id.startswith(prefix + "-"):
            return atype
    return None


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

_INDEX_CACHE: dict[str, dict[str, Any]] | None = None

def get_index(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Return the cached index, building it if it doesn't exist or if forced."""
    global _INDEX_CACHE
    if _INDEX_CACHE is None or force_refresh:
        _INDEX_CACHE = build_index()
    return _INDEX_CACHE

def build_index() -> dict[str, dict[str, Any]]:
    """Scan all _blueprint/ markdown files and return a dict keyed by artifact id.

    Each value is:
        {
            "type": "Goal" | "Feature" | ...,
            "path": Path,
            "meta": { ...frontmatter fields... },
            "body_snippet": str (first 200 chars)
        }
    """
    index: dict[str, dict[str, Any]] = {}
    for md_path in BLUEPRINT_ROOT.rglob("*.md"):
        meta = read_frontmatter(md_path)
        artifact_id = meta.get("id")
        if not artifact_id:
            continue
        atype = _type_from_id(str(artifact_id))
        if not atype:
            continue
        body = read_body(md_path)
        index[str(artifact_id)] = {
            "type":         atype,
            "path":         md_path,
            "meta":         meta,
            "body_snippet": body[:200],
        }
    return index


def get_by_id(artifact_id: str, index: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return a single artifact dict or None if not found."""
    idx = index if index is not None else get_index()
    return idx.get(str(artifact_id))


def get_by_type(atype: str, index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return all artifacts of a given type (e.g. 'Goal', 'Task')."""
    idx = index if index is not None else get_index()
    return [v for v in idx.values() if v["type"] == atype]


def get_children(parent_id: str, index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return all artifacts whose parent_goal / parent_feat / parent_uc == parent_id."""
    idx = index if index is not None else get_index()
    results = []
    for v in idx.values():
        meta = v["meta"]
        for key in ("parent_goal", "parent_feat", "parent_uc", "origin"):
            if str(meta.get(key, "")) == str(parent_id):
                results.append(v)
                break
    return results


def get_trace_path(artifact_id: str, index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Walk upward from artifact_id to the root Goal, returning the chain."""
    idx = index if index is not None else get_index()
    chain: list[dict[str, Any]] = []
    current_id = str(artifact_id)
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = idx.get(current_id)
        if not node:
            break
        chain.append(node)
        meta = node["meta"]
        parent = None
        for key in ("parent_uc", "parent_feat", "parent_goal", "origin"):
            val = meta.get(key)
            if val:
                parent = str(val)
                break
        current_id = parent  # type: ignore[assignment]
    return chain  # [artifact, ..., Goal]


def to_json(index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Serialize the index to a JSON-safe list (paths converted to strings)."""
    idx = index if index is not None else get_index()
    result = []
    for artifact_id, entry in idx.items():
        result.append({
            "id":           artifact_id,
            "type":         entry["type"],
            "path":         str(entry["path"]),
            "meta":         entry["meta"],
            "body_snippet": entry["body_snippet"],
        })
    return result
