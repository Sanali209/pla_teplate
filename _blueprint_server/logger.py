"""
logger.py — Centralised Rich console logger for Blueprint MCP Server.
All server modules import `log` from here.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text

_theme = Theme({
    "tool":     "bold cyan",
    "resource": "bold blue",
    "prompt":   "bold magenta",
    "ok":       "bold green",
    "warn":     "bold yellow",
    "error":    "bold red",
    "trace":    "dim white",
    "gate":     "bold orange3",
    "info":     "white",
})

# All logs go to stderr so they don't pollute the stdio MCP transport on stdout
console = Console(stderr=True, theme=_theme)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Public log functions (import these in other modules)
# ---------------------------------------------------------------------------

def server_start(name: str, version: str) -> None:
    console.print(Panel(
        f"[ok]Blueprint MCP Server[/ok]  [trace]v{version}[/trace]\n"
        f"[trace]stdio transport · {_ts()} UTC[/trace]",
        title="🚀 Starting",
        border_style="green",
    ))


def tool_call(name: str, args: dict) -> None:
    args_str = "  ".join(f"[trace]{k}[/trace]=[info]{_short(v)}[/info]" for k, v in args.items())
    console.print(f"[trace]{_ts()}[/trace] [tool]TOOL[/tool] [bold]{name}[/bold]  {args_str}")


def tool_ok(name: str, msg: str) -> None:
    console.print(f"[trace]{_ts()}[/trace] [ok]  ✓[/ok] [bold]{name}[/bold]  {msg}")


def tool_error(name: str, msg: str) -> None:
    console.print(f"[trace]{_ts()}[/trace] [error]  ✗[/error] [bold]{name}[/bold]  {msg}")


def gate_blocked(rule: str, detail: str) -> None:
    console.print(f"[trace]{_ts()}[/trace] [gate]GATE[/gate] [{rule}] {detail}")


def resource_read(uri: str) -> None:
    console.print(f"[trace]{_ts()}[/trace] [resource]RES[/resource]  {uri}")


def prompt_load(name: str, path: str) -> None:
    console.print(f"[trace]{_ts()}[/trace] [prompt]PROMPT[/prompt] {name}  [trace]← {path}[/trace]")


def validate_result(error_count: int) -> None:
    if error_count == 0:
        console.print(f"[trace]{_ts()}[/trace] [ok]VALID[/ok]  All artifacts pass traceability checks")
    else:
        console.print(f"[trace]{_ts()}[/trace] [error]VALID[/error]  {error_count} issue(s) found")


def status_change(artifact_id: str, old: str, new: str) -> None:
    color = "ok" if new == "APPROVED" else ("error" if new in ("NEEDS_FIX", "REJECTED") else "warn")
    console.print(
        f"[trace]{_ts()}[/trace] [bold]STATUS[/bold]  {artifact_id}  "
        f"[trace]{old}[/trace] → [{color}]{new}[/{color}]"
    )


def artifact_created(artifact_id: str, atype: str, path: str) -> None:
    console.print(
        f"[trace]{_ts()}[/trace] [ok]CREATE[/ok] [{atype}] [bold]{artifact_id}[/bold]  "
        f"[trace]{path}[/trace]"
    )


def _short(v: object, max_len: int = 60) -> str:
    s = str(v)
    return s if len(s) <= max_len else s[:max_len] + "…"
