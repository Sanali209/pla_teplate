# File Naming Conventions — Blueprint Protocol

## Purpose
These rules ensure every agent-generated file lands in the correct directory
and can be found by the MCP artifact index (`artifact_index.py`).

---

## ID Prefixes and Directories

| Artifact Type | ID Prefix | Storage Directory |
|---|---|---|
| Goal | `GL-` | `_blueprint/dev_docs/brain/` |
| Feature | `FT-` | `_blueprint/dev_docs/logic/` |
| Research | `RS-` | `_blueprint/dev_docs/brain/R_D_Archive/` |
| Use Case | `UC-` | `_blueprint/dev_docs/logic/` |
| Task | `TSK-` | `_blueprint/execution/backlog/` |
| UML Draft | `UML-` | `_blueprint/dev_docs/architecture/UML_Models/Drafts/` |
| UML Approved | `UML-` | `_blueprint/dev_docs/architecture/UML_Models/Approved/` |
| Review Log | `STATUS-` / `CRITIC-` | `_blueprint/dev_docs/quality/Review_Logs/` |
| User Feedback | `FB-` | `_blueprint/inbound/User_Feedback/` |

---

## File Naming Pattern

```
{ID}.md
```

Examples:
- `GL-001.md` — first goal
- `FT-003.md` — third feature
- `UC-012.md` — twelfth use case
- `TSK-005.md` — fifth task

---

## Numbering Rules

- IDs are **zero-padded to 3 digits**: `GL-001`, not `GL-1`.
- IDs are **globally unique per prefix**. Never reuse a retired ID.
- Use sequential integers. Do NOT skip numbers.
- Before creating a new artifact, call `validate_all()` to check what ID is next.

---

## Prohibited Actions

1. ❌ Do NOT create a Task (`TSK-`) file without a `parent_uc` in its frontmatter.
2. ❌ Do NOT place files in the wrong directory (e.g., Goals in logic/).
3. ❌ Do NOT create artifacts without the YAML frontmatter block.
4. ❌ Do NOT hardcode paths — always use the `BLUEPRINT_ROOT` from `config.py`.
5. ❌ Do NOT create duplicate IDs.

---

## Markdown Links in Artifacts

All cross-references between artifacts MUST use relative paths:

```markdown
See parent goal: [GL-001](../../brain/GL-001.md)
Related use case: [UC-003](./UC-003.md)
```

This ensures the documents remain valid even if the repo root changes.
