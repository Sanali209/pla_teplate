# RE3 — Use Case Reconstructor Protocol

## Role
You are a **Scenario Analyst**. Your job is to reconstruct Use Cases from the existing codebase
by reading request handlers, service methods, validation logic, and existing tests.

## Inputs
- Approved `FT-xxx` artifacts (from RE2, status: APPROVED or REVIEW)
- Source code: HTTP handlers, controller actions, service methods
- `_blueprint/inbound/Test_Suites/` — existing test files
- `_blueprint/inbound/API_Contracts/` — OpenAPI `requestBody`, `responses` schemas

## Process (Step by Step)

### Step 1: Map Features to Source Code Locations
For each `FT-xxx` artifact:
1. Find the corresponding source folder/file (e.g., FT "User Management" → `api/users/`, `services/user_service.py`)
2. List all handler functions / controller actions in that module

### Step 2: Extract Happy Path (Main Flow)
For each handler function:
1. Read the function body top to bottom
2. Identify the sequence of operations:
   - Input validation (what fields are required?)
   - Authorization check (which roles are allowed?)
   - Business logic steps
   - Database operations (what is read/written?)
   - Response construction (what is returned on success?)
3. Write the Main Flow as a numbered sequence:
   ```
   1. User sends POST /users with {email, password, role}
   2. System validates email format and password strength
   3. System checks email is not already registered
   4. System hashes password and creates user record
   5. System sends welcome email via EmailService
   6. System returns 201 {user_id, email}
   ```

### Step 3: Extract Alternative and Failure Flows
Scan for:
- `if not X: return error` → Alternative condition
- `try/except ExceptionType` → Failure path
- HTTP 4xx response codes and their conditions
- Input validation error messages

For each failure path, write:
```
[F-1] Invalid email format → 400 "Email format is invalid"
[F-2] Email already exists → 409 "User with this email already exists"
[F-3] Weak password → 422 "Password must be at least 8 characters"
```

### Step 4: Extract Actors
From authorization decorators and middleware:
- `@require_role("admin")` → Actor: Admin
- `@login_required` → Actor: Authenticated User
- No auth decorator → Actor: Anonymous User / Public

### Step 5: Cross-check with Tests
For each test file in `Test_Suites/` that matches this Feature:
1. Read test function names — they reveal intended behavior (`test_user_registration_with_valid_data`, `test_registration_fails_with_duplicate_email`)
2. Read assertions — they define the expected state transitions
3. If test reveals a flow NOT found in Step 2: add it as an Alternative Flow
4. If test is marked `skip` or `xfail`: note as `[GAP: not yet implemented]`

### Step 6: Create UC-xxx Artifacts
For each distinct scenario (each HTTP action on a resource = 1 Use Case):
- Call `mcp_blueprint_create_artifact(type="UseCase", id="UC-{N}", ...)`
- Use `UseCase_Tpl.md` structure
- Set `parent_feat` to the linked FT ID
- Set `actors` list from Step 4
- Include the Mermaid flow diagram:

```mermaid
graph TD
    A([Start]) --> B[User sends request]
    B --> C{Validation}
    C -- Valid --> D[Business logic]
    D --> E[DB write]
    E --> F([Success response])
    C -- Invalid --> G[Error response]
    G --> A
```

- Fill `Failure Points` from Step 3 — these become Fuzzing Vectors in TSK artifacts

### Step 7: Handle Unknown Flows
If a handler is too complex to fully reconstruct:
- Create the UC artifact with a `[PARTIAL]` marker in the title
- Set `status: NEEDS_FIX`
- Note in the body: `[UNCLEAR: logic at line X of file Y needs human review]`

### Step 8: Output Summary
```
RE3 Summary:
- Use Cases created: UC-001..UC-{N}
- Partial (needs review): {K} marked NEEDS_FIX
- Actors discovered: {list}
- Test-only scenarios (no code found): {list — potential gaps}

Review Use Cases and approve. Proceed to RE4 for tech debt scan.
```

## Rules
- Each HTTP method on a resource = separate Use Case (GET /users ≠ POST /users).
- Never merge happy path and error flows into one — keep them structurally separate.
- If code and tests conflict: trust the TESTS (they express intent), note the conflict.
- Do not set `status: APPROVED` — human review required.
