"""
fs_reader.py — Shared utility for reading YAML frontmatter from Blueprint markdown artifacts.
Used by both the MCP Server (agent) and the PySide2 GUI (user).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

BLUEPRINT_ROOT: Path = Path(__file__).parent.parent / "_blueprint"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def read_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML front-matter block from a markdown file.
    Returns an empty dict if no front-matter is found."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def read_body(path: Path) -> str:
    """Return the markdown content after the YAML front-matter block."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return FRONTMATTER_RE.sub("", text, count=1).strip()


def write_frontmatter(path: Path, metadata: dict[str, Any], body: str = "") -> None:
    """Write (or overwrite) the YAML front-matter + body to a markdown file.
    Creates parent directories if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_block = yaml.dump(metadata, allow_unicode=True, sort_keys=False)
    content = f"---\n{yaml_block}---\n\n{body}"
    path.write_text(content, encoding="utf-8")


def patch_frontmatter(path: Path, updates: dict[str, Any]) -> None:
    """Merge `updates` into the existing YAML front-matter of a file."""
    meta = read_frontmatter(path)
    body = read_body(path)
    meta.update(updates)
    write_frontmatter(path, meta, body)
