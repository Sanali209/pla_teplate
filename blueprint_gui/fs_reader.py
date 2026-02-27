"""
fs_reader.py — GUI-side copy of the shared fs_reader utility.
Reads YAML frontmatter and body from _blueprint/ markdown artifacts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BLUEPRINT_ROOT: Path = Path(__file__).parent.parent / "_blueprint"


def read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def read_body(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return FRONTMATTER_RE.sub("", text, count=1).strip()


def patch_frontmatter(path: Path, updates: dict[str, Any]) -> None:
    import yaml as _yaml
    meta = read_frontmatter(path)
    body = read_body(path)
    meta.update(updates)
    yaml_block = _yaml.dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{yaml_block}---\n\n{body}", encoding="utf-8")
