---
id: UML-{{NUMBER}}
title: "{{DIAGRAM TITLE}}"
type: Sequence    # UseCase | Sequence | Class | State | Activity
status: DRAFT     # DRAFT → approved → moved to Approved/ folder
parent_uc: UC-{{NUMBER}}
created_at: {{ISO_TIMESTAMP}}
---

# UML Draft: {{DIAGRAM TITLE}}

## Diagram

```plantuml
@startuml
' Change diagram type to match `type` field above.
' UseCase example:
actor User
rectangle System {
  usecase "{{Action}}" as UC1
}
User --> UC1
@enduml
```

## Review Notes
<!-- Human: add critique here. Agent: read this section in R4_UML_Validator protocol -->

## Validation Checklist (R4)
- [ ] All actors are defined in parent UseCase `actors` field
- [ ] All failure paths from `Failure Points` are represented
- [ ] No logical dead-ends (states with no exit)
- [ ] Sequence diagram shows return messages (not just calls)
