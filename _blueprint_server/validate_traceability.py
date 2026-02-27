"""
validate_traceability.py — Checks that every artifact's parent reference points to an existing artifact.
Returns a structured report of broken links (orphans) and missing required fields.
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
    "UseCase":  ["id", "title", "status", "parent_feat"],
    "Task":     ["id", "title", "status", "parent_uc"],
}

# Status transitions: which statuses are locked by parent status
BLOCKED_BY: dict[str, list[str]] = {
    "Task": ["DRAFT", "REVIEW"],  # Task cannot be DONE if parent UC is not APPROVED
}


@dataclass
class ValidationError:
    artifact_id: str
    artifact_type: str
    path: str
    error_type: str   # "ORPHAN", "MISSING_FIELD", "BLOCKED_BY_PARENT"
    detail: str


@dataclass
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def summary(self) -> str:
        if not self.errors:
            return "✅ All artifacts are valid. No traceability issues found."
        lines = [f"❌ Found {len(self.errors)} issue(s):"]
        for err in self.errors:
            lines.append(f"  [{err.error_type}] {err.artifact_id} ({err.artifact_type}): {err.detail}")
        return "\n".join(lines)


def validate_traceability(index: dict[str, Any] | None = None) -> ValidationReport:
    """Run all traceability checks on the current artifact index."""
    idx = index if index is not None else build_index()
    report = ValidationReport()

    for artifact_id, entry in idx.items():
        atype = entry["type"]
        meta  = entry["meta"]
        path  = str(entry["path"])

        # 1. Check required fields
        for required_field in REQUIRED_FIELDS.get(atype, []):
            if not meta.get(required_field):
                report.errors.append(ValidationError(
                    artifact_id=artifact_id,
                    artifact_type=atype,
                    path=path,
                    error_type="MISSING_FIELD",
                    detail=f"Required field '{required_field}' is missing or empty.",
                ))

        # 2. Check that parent references resolve
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

        # 3. Gate check: Tasks cannot be created if parent UseCase is not APPROVED
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

    return report
