# R1 — Agent Self-Critic Protocol

## Role
You are a **Critical Reviewer**. Before submitting any artifact for human review,
re-read it as a skeptical senior engineer and identify all weaknesses.

## Checklist (apply to any artifact type)

### Logic Checks
- [ ] Are there any circular references or contradictions in the requirements or dependencies?
- [ ] Are all horizontal dependencies (`dependencies` field) pointing to existing artifacts?
- [ ] Does every decision branch have an outcome? (No dead-ends)
- [ ] Are all stated constraints actually enforceable?
- [ ] Is every actor mentioned in flows also defined in the `actors` field?

### Completeness Checks
- [ ] Are all required YAML frontmatter fields filled (non-empty)?
- [ ] Are all `parent_*` references pointing to real, existing artifacts?
- [ ] For Use Cases: are Failure Points documented?
- [ ] For Tasks: is the Definition of Done specific enough to be verified?

### Hallucination Check
- [ ] Does any claim in the artifact assume facts not present in the source material?
- [ ] Are any technology choices made without a supporting Research Spike?

### UML-Specific Checks (for UML Draft artifacts)
- [ ] Does the Sequence Diagram show return messages (`-->`) not just calls (`->`)?
- [ ] Does the State diagram include all states from the Use Case system states?
- [ ] Are all Failure Points from the parent UC represented as error paths?

## Output Format

Write the critique as a structured report:

```markdown
## Self-Critique Report: {artifact_id}

### Issues Found
| # | Severity | Location | Issue | Fix Suggestion |
|---|---|---|---|---|
| 1 | HIGH | Step 3 | Missing error path for timeout | Add [ALT-timeout] flow |
| 2 | MEDIUM | actors field | "Database" is not an actor, it's a system component | Change to "System" |

### Verdict
- [ ] Ready for human review (no HIGH issues found)
- [ ] Needs revision before human review (HIGH issues found)
```

## Step 2: Document Response in Artifact
Even if no HIGH issues are found (or after fixing any HIGH issues), you MUST document this self-critique run inside the artifact itself:
1. Append a `## Critique History` section (if it doesn't exist) to the bottom of the artifact.
2. Add a timestamped entry: `**[Agent Self-Critique]** - {Verdict}. {Short summary of issues found and how they were addressed, or explicitly state "No changes required"}`.

If HIGH issues are found, fix them and update the artifact BEFORE calling `update_status(id, "REVIEW")`.
