"""
validate_traceability.py — Checks that every artifact's parent reference points to an existing artifact.
Returns a structured report of broken links (orphans), missing required fields,
forbidden status transitions, gate violations, and duplicate IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from artifact_index import build_index


# YAML fields that are treated as parent references
PARENT_FIELDS = ("parent_goal", "parent_feat", "parent_uc", "origin")

# Required YAML fields per artifact type
REQUIRED_FIELDS: dict[str, list[str]] = {
    "Goal":     ["id", "title", "status"],
    "Feature":  ["id", "title", "status", "parent_goal"],
    "Research": ["id", "hypothesis", "verdict", "parent_goal"],
    "UseCase":  ["id", "title", "status", "parent_feat", "dependencies"],
    "Task":     ["id", "title", "status", "parent_uc"],
}

# Valid status values (must match VALID_STATUSES in agent_tools.py)
VALID_STATUSES = {
    "DRAFT", "REVIEW", "APPROVED", "NEEDS_FIX",
    "BLOCKED", "DONE", "ARCHIVED", "REJECTED"
}

# Forbidden status transitions: {from_status: frozenset(disallowed_to_statuses)}
FORBIDDEN_TRANSITIONS: dict[str, frozenset[str]] = {
    "APPROVED": frozenset({"DRAFT", "REVIEW"}),  # Must go through NEEDS_FIX
    "DONE":     frozenset(VALID_STATUSES - {"ARCHIVED"}),  # Terminal — only ARCHIVED allowed
}


@dataclass
class ValidationError:
    artifact_id: str
    artifact_type: str
    path: str
    error_type: str   # "ORPHAN", "MISSING_FIELD", "BLOCKED_BY_PARENT", "GATE_VIOLATION",
                      # "DUPLICATE_ID", "FORBIDDEN_TRANSITION", "SOFT_WARNING"
    detail: str
    severity: str = "ERROR"   # "ERROR" | "WARNING"


@dataclass
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(e.severity == "ERROR" for e in self.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "WARNING")

    def summary(self) -> str:
        if not self.errors:
            return "✅ All artifacts are valid. No traceability issues found."
        lines = []
        errors   = [e for e in self.errors if e.severity == "ERROR"]
        warnings = [e for e in self.errors if e.severity == "WARNING"]
        if errors:
            lines.append(f"❌ Found {len(errors)} error(s):")
            for err in errors:
                lines.append(f"  [ERROR/{err.error_type}] {err.artifact_id} ({err.artifact_type}): {err.detail}")
        if warnings:
            lines.append(f"⚠️  Found {len(warnings)} warning(s):")
            for w in warnings:
                lines.append(f"  [WARN/{w.error_type}] {w.artifact_id} ({w.artifact_type}): {w.detail}")
        return "\n".join(lines)


def validate_traceability(index: dict[str, Any] | None = None) -> ValidationReport:
    """Run all traceability checks on the current artifact index."""
    idx = index if index is not None else build_index()
    report = ValidationReport()

    # ── G4: Duplicate ID check ────────────────────────────────────────────────
    # The index build uses last-wins; independently scan files for collisions
    seen_ids: dict[str, list[str]] = {}
    for artifact_id, entry in idx.items():
        seen_ids.setdefault(artifact_id, []).append(str(entry["path"]))
    # Note: index deduplicates by default; to catch real-disk duplicates we
    # check if two different paths share the same id in frontmatter by rescanning
    # (the index already handles it, but we add a warning for awareness)
    # For now flag if any entry path basename doesn't start with the id prefix
    for artifact_id, entry in idx.items():
        fname = entry["path"].stem
        if fname != artifact_id:
            report.errors.append(ValidationError(
                artifact_id=artifact_id,
                artifact_type=entry["type"],
                path=str(entry["path"]),
                error_type="DUPLICATE_ID",
                detail=(
                    f"File name '{fname}.md' does not match declared id '{artifact_id}'. "
                    "Rename file or fix the id field."
                ),
            ))

    for artifact_id, entry in idx.items():
        atype = entry["type"]
        meta  = entry["meta"]
        path  = str(entry["path"])

        # ── G5: Check required fields ─────────────────────────────────────────
        for required_field in REQUIRED_FIELDS.get(atype, []):
            if not meta.get(required_field):
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="MISSING_FIELD",
                    detail=f"Required field '{required_field}' is missing or empty.",
                ))

        # ── G3: Check that parent references resolve ───────────────────────────
        for pfield in PARENT_FIELDS:
            parent_id = meta.get(pfield)
            if parent_id and str(parent_id) not in idx:
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="ORPHAN",
                    detail=f"Parent reference '{pfield}: {parent_id}' does not exist in the index.",
                ))

        # ── G8: Dependency Check (Horizontal Traceability) ────────────────────
        deps = meta.get("dependencies")
        if deps is None:
            # Not an error, just assume empty for validation
            deps = []
        
        if isinstance(deps, str):
             # Handle string representation of list if parsed lazily
             deps = [d.strip() for d in deps.strip("[]").split(",") if d.strip()]
        
        for dep_id in deps:
            if dep_id not in idx:
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="ORPHAN",
                    detail=f"Dependency '{dep_id}' does not exist in the index.",
                ))
            elif meta.get("status") == "DONE":
                dep_entry = idx[dep_id]
                if dep_entry["meta"].get("status") != "DONE":
                    report.errors.append(ValidationError(
                        artifact_id=artifact_id,
                        artifact_type=atype,
                        path=path,
                        error_type="GATE_VIOLATION",
                        detail=f"Cannot mark '{artifact_id}' as DONE while dependency '{dep_id}' is '{dep_entry['meta'].get('status')}'.",
                    ))

        # ── G1: Task Gate ─────────────────────────────────────────────────────
        if atype == "Task":
            parent_uc_id = str(meta.get("parent_uc", ""))
            parent = idx.get(parent_uc_id)
            if parent and parent["meta"].get("status") not in ("APPROVED",):
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="BLOCKED_BY_PARENT",
                    detail=(
                        f"Task created while parent UseCase '{parent_uc_id}' "
                        f"has status '{parent['meta'].get('status')}' (must be APPROVED)."
                    ),
                ))

        # ── G2: Analysis Gate — Feature with research_required must have SUCCESS RS ──
        if atype == "UseCase":
            parent_feat_id = str(meta.get("parent_feat", ""))
            feat = idx.get(parent_feat_id)
            if feat and feat["meta"].get("research_required") in (True, "true", "True"):
                # Check if any Research artifact links to this feature's parent goal
                # with verdict SUCCESS or PENDING
                feat_goal = str(feat["meta"].get("parent_goal", ""))
                linked_rs = [
                    e for e in idx.values()
                    if e["type"] == "Research"
                    and str(e["meta"].get("parent_goal", "")) == feat_goal
                    and e["meta"].get("verdict") in ("SUCCESS", "PENDING")
                ]
                if not linked_rs:
                    report.errors.append(ValidationError(
                        artifact_id=artifact_id,
                        artifact_type=atype,
                        path=path,
                        error_type="GATE_VIOLATION",
                        detail=(
                            f"Parent Feature '{parent_feat_id}' has research_required: true "
                            f"but no Research Spike with verdict SUCCESS or PENDING was found "
                            f"for goal '{feat_goal}'. Run P2 Research protocol first."
                        ),
                ))

    # ── G9: Circular Dependency Check ─────────────────────────────────────────
    graph: dict[str, list[str]] = {}
    for aid, entry in idx.items():
        meta = entry["meta"]
        deps = meta.get("dependencies", [])
        if isinstance(deps, str):
            deps = [d.strip() for d in deps.strip("[]").split(",") if d.strip()]
        graph[aid] = deps

    def find_cycle(node_id: str, visited: set[str], stack: set[str]) -> list[str] | None:
        visited.add(node_id)
        stack.add(node_id)
        for neighbor in graph.get(node_id, []):
            if neighbor not in visited:
                cycle = find_cycle(neighbor, visited, stack)
                if cycle:
                    cycle.append(node_id)
                    return cycle
            elif neighbor in stack:
                return [neighbor, node_id]
        stack.remove(node_id)
        return None

    visited_nodes: set[str] = set()
    for art_id in graph:
        if art_id not in visited_nodes:
            cycle_found = find_cycle(art_id, visited_nodes, set())
            if cycle_found:
                # cycle_found is [start, ..., end, start] in reverse order
                cycle_str = " -> ".join(reversed(cycle_found))
                entry = idx[art_id]
                report.errors.append(ValidationError(
                    artifact_id=art_id,
                    artifact_type=entry["type"],
                    path=str(entry["path"]),
                    error_type="GATE_VIOLATION",
                    detail=f"Circular dependency detected: {cycle_str}",
                ))
                break # Report first cycle found

    # ── W3: Soft Warning — NEEDS_FIX without feedback file ────────────────
        status = str(meta.get("status", ""))
        if status in ("NEEDS_FIX", "REJECTED"):
            from config import BLUEPRINT_ROOT
            fb_path = BLUEPRINT_ROOT / "inbound" / "User_Feedback" / f"FB-{artifact_id}.md"
            if not fb_path.exists():
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="SOFT_WARNING",
                    detail=(
                        f"Artifact has status '{status}' but no feedback file "
                        f"'FB-{artifact_id}.md' exists. Agent cannot determine fix reason."
                    ),
                    severity="WARNING",
                ))

    return report


def check_transition(artifact_id: str, current_status: str, new_status: str) -> str | None:
    """
    Check if a status transition is allowed.
    Returns an error message string if forbidden, or None if allowed.
    """
    forbidden = FORBIDDEN_TRANSITIONS.get(current_status)
    if forbidden and new_status in forbidden:
        if current_status == "DONE":
            return (
                f"Forbidden transition: '{artifact_id}' is DONE (terminal state). "
                "Only ARCHIVED is allowed. Create a new artifact for a new version."
            )
        return (
            f"Forbidden transition: '{artifact_id}' cannot move from {current_status} → {new_status}. "
            f"Use NEEDS_FIX first, then fix and resubmit to REVIEW."
        )
    return None
