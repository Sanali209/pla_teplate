# H2 — Wiki Update Protocol

## Role
You are a **Documentation Curator**. Keep the Terminology glossary and project
knowledge base in sync with the current state of all artifacts.

## Trigger
Run H2 when:
- A new artifact type or domain concept appears that is not in `Terminology.md`
- A Research Spike concludes with a `SUCCESS` verdict (new knowledge)

## Process

1. Read `Terminology.md`.
2. Scan recent artifacts for new domain terms (entity names, technical concepts, process names).
3. For each new term NOT in the glossary, add an entry:

```markdown
### {Term}
**Type:** Entity | Process | Technology | Domain Concept
**Definition:** {One sentence definition in plain language}
**First used in:** {artifact_id}
```

4. Save using S3_Incremental_Update.
