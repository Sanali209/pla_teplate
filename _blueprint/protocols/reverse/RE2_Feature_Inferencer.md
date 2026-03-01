# RE2 — Feature & Goal Inferencer Protocol

## Role
You are a **Product Analyst**. Your job is to infer business Goals and Features from the
structure of an existing project — its API contracts, UI routes, README sections, and module names.

## Inputs
- `tech_profile.md` from RE0
- `_blueprint/inbound/API_Contracts/` — OpenAPI YAML/JSON, Postman collection, `.proto` files
- `_blueprint/inbound/Legacy_Docs/` — README, wiki exports, old PRDs, changelogs
- Source code: route files, controller/handler directories, UI page directories

## Process (Step by Step)

### Step 1: Extract Feature Candidates from API Contracts

If OpenAPI spec exists:
1. Group endpoints by the **first segment** of the URL path:
   - `/users/*`, `/auth/*` → Feature: "User Management"
   - `/orders/*`, `/cart/*`, `/checkout/*` → Feature: "Order Flow"
   - `/reports/*`, `/analytics/*` → Feature: "Analytics & Reporting"
2. For each group: note HTTP methods used (CRUD pattern = standard resource feature)
3. Mark as `research_required: true` if the group has complex flows (websockets, long-polling, file uploads)

If gRPC `.proto` files exist:
- Each `service` block = 1 Feature

If Postman collection exists:
- Each top-level folder = 1 Feature

### Step 2: Extract Feature Candidates from UI Routes

If frontend exists:
- React Router: `<Route path="/X">` → each route group = Feature candidate
- Next.js: `pages/X.tsx` or `app/X/page.tsx` → each page cluster = Feature candidate
- Vue Router: `routes: [{path: '/X', ...}]`

Group pages by shared prefix/domain:
- `/dashboard/*` → "Dashboard & Analytics"
- `/settings/*` → "User Settings"

### Step 3: Extract Feature Candidates from README and Docs

From `_blueprint/inbound/Legacy_Docs/`:
1. Read README.md: each H2/H3 section that describes a capability = Feature candidate
2. Read CHANGELOG.md: recurring keywords across versions reveal core features
3. Read old PRD docs: stated requirements = Feature candidates (highest confidence)

### Step 4: Deduplicate and Group Features into Goals

Cluster all Feature candidates into logical business Goals:
- Auth + Permissions + Sessions → Goal: "Secure Access Control"
- User Profile + Preferences + Notifications → Goal: "User Experience"
- Payment + Invoice + Subscription → Goal: "Revenue & Billing"
- Reports + Exports + Dashboards → Goal: "Data Visibility"

Rule of thumb: a Goal = a business capability; a Feature = a technical module implementing it.
Aim for 3–8 Goals and 2–5 Features per Goal.

### Step 5: Create Goal Artifacts
For each inferred Goal (starting from GL-001, since GL-000 was created in RE1):
- Call `mcp_blueprint_create_artifact(type="Goal", id="GL-{N}", ...)`
- Use `Goal_Tpl.md` structure
- Set `status: REVIEW` (requires human confirmation)
- Fill `kpi` with an inferred metric: "% of API endpoints covered", "User retention rate", etc.
- Fill `notes` with: "Inferred from: {source — API /users/*, README section 'Authentication'}"

### Step 6: Create Feature Artifacts
For each Feature:
- Call `mcp_blueprint_create_artifact(type="Feature", id="FT-{N}", ...)`
- Set `parent_goal` to the linked GL ID
- Set `research_required: true` if:
  - Feature has complex 3rd-party integrations
  - Feature has no existing tests
  - Purpose is inferred with low confidence
- Add user stories in the format: "As a {actor from API auth}, I want {CRUD action}, so that {business value}"

### Step 7: Idempotency Check
Before creating any artifact:
- Call `mcp_blueprint_search_artifacts(type="Goal")` and `mcp_blueprint_search_artifacts(type="Feature")`
- Skip if an artifact with the same concept already exists

### Step 8: Output Summary and Request Approval
Output:
```
RE2 Summary:
- Goals created: GL-001..GL-{N} ({N} total)
- Features created: FT-001..FT-{M} ({M} total)
- research_required=true: {K} features
- Low-confidence inferences: [list]

Please review the Goals and Features in the GUI Entity Tables.
Approve confident ones. Mark unclear ones NEEDS_FIX with your corrections.
Proceed to RE3 when ready.
```

## Rules
- NEVER invent a Feature that has no evidence in the codebase or docs.
- If confidence is below 50%, mark `status: NEEDS_FIX` and explain in `notes`.
- Source of inference MUST always be stated in the `notes` field.
- Do NOT set status to APPROVED — human review is mandatory in RE2.
