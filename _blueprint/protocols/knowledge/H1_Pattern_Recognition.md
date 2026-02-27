# H1 — Pattern Recognition Protocol

## Role
You are a **Knowledge Engineer**. After a successful sprint or phase completion,
extract reusable patterns and add them to the project Knowledge Base.

## Trigger
Run H1 when:
- An artifact transitions from `NEEDS_FIX` → `APPROVED` (a fix that worked)
- End of sprint (any task batch marked `DONE`)

## Process

1. Review the recent `Review_Logs/STATUS-*.md` files for the completed phase.
2. For each `NEEDS_FIX → APPROVED` transition, ask:
   - What was the mistake? (Anti-Pattern candidate)
   - What was the fix? (Design Pattern candidate)
3. Read current `Design_Patterns.md` and `Anti_Patterns.md`.
4. If the pattern is NOT yet listed, add an entry.
5. Use S3_Incremental_Update to patch the brain files.

## Pattern Entry Format

```markdown
### DP-{N}: {Pattern Name}
**Context:** When doing X in phase Y
**Solution:** Do Z instead of W
**Evidence:** Seen in artifacts [{ids}]
```
