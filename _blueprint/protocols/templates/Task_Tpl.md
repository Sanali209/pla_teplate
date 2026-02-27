---
id: TSK-{{NUMBER}}
title: "{{TASK TITLE}}"
status: DRAFT
parent_uc: UC-{{NUMBER}}
assignee: ""
layer: backend   # backend | frontend | infra | qa
created_at: {{ISO_TIMESTAMP}}
revision_count: 1
---

# Task: {{TASK TITLE}}

## Context (Reverse Path)
- **Use Case:** [UC-xxx](../../logic/UC-xxx.md)
- **Feature:** [FT-xxx](../../logic/FT-xxx.md)
- **Goal:** [GL-xxx](../../brain/GL-xxx.md)

## Description
{{What exactly needs to be built or done? Be precise enough for a developer to estimate.}}

## Implementation Steps
*(To be filled by the Executing Agent during E1_Sprint_Execution)*
- [ ] Step 1...
- [ ] Step 2...

## Acceptance Criteria
- [ ] {{Criterion 1 — testable condition}}
- [ ] {{Criterion 2}}

## Fuzzing Vectors (QA)
<!-- Derived from Failure Points in parent Use Case -->
- **Input field `{{field}}`:** test with `{{bad_value_1}}`, `{{bad_value_2}}`
- **Edge case:** {{description}}

## Definition of Done
- [ ] Code written and reviewed
- [ ] Unit tests pass
- [ ] Linked Use Case scenario manually verified
- [ ] No new validation errors from `validate_all()`

## Critique History
