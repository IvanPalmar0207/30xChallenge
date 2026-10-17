# PayBlood — Phase 2, Slice 1: Organizations and Tenant-Scoped Authentication

Reference: `docs/implementation-contract.md` (unchanged invariants).

## Specs

- **S1 — Organization model**: UUID primary key; `name`; explicit status
  (`active`/`inactive`); `created_at`/`updated_at`.
- **S2 — Membership model**: `user` FK (existing Django user model; do not
  change `AUTH_USER_MODEL` casually — explain first); `organization` FK;
  organization-scoped `role`; `is_active`; timestamps. Database-level unique
  constraint on (user, organization). A user may belong to multiple
  organizations with a different role in each.
- **S3 — Roles**: exactly `FINANCE_ADMIN`, `OPERATOR`, `APPROVER`, `AUDITOR`.
  Global superadmin is a separate concept; admin/superuser status must never
  implicitly grant membership or approval authority. No business permissions
  beyond a clear, testable baseline.
- **S4 — Security invariants**: protected endpoints require authentication;
  never trust client-supplied organization IDs as authorization; resolve the
  user's active membership server-side; no access without an active
  membership; inactive organizations deny normal operations; no cross-tenant
  access via URL/query/header/body tampering; enforcement lives at the API
  layer and is tested (never Angular guards); consistent authorization
  behavior that does not disclose other organizations' existence; no implicit
  approval authority through superuser/staff; no sensitive information in
  errors or logs. No unsafe default organization; no automatic membership
  from a client-provided organization ID.
- **S5 — API baseline**: `/api/v1/` prefix; `GET /api/v1/organizations/`
  (accessible organizations); `GET /api/v1/organizations/{id}/` (own active
  membership only); `GET /api/v1/auth/me/` (safe profile + active memberships
  with roles). Reuse/extend existing auth rather than re-implementing login or
  token refresh; DRF serializers and permissions; server-side scoped queries.
- **S6 — Tests**: (1) anonymous denied; (2) list only active-membership
  organizations; (3) member retrieves own organization; (4) org A user cannot
  retrieve org B by UUID; (5) inactive memberships grant nothing; (6) inactive
  organizations unusable; (7) no-membership user blocked; (8) membership
  uniqueness enforced; (9) different roles per user in one organization;
  (10) admin status alone grants neither membership nor approval authority;
  (11) `/auth/me/` exposes no passwords, tokens, secrets, or unrelated
  organization data. Tests verify real backend behavior, not serializer
  output alone.
- **S7 — Migrations**: proper migrations; preserve existing data and
  migrations; no reset/delete; no destructive shortcuts; tests on the
  configured local database; do not claim PostgreSQL verified unless a
  PostgreSQL-backed test ran.
- **S8 — Quality**: scope limited to this slice; follow the existing layout
  (`backend/apps/`); English identifiers/comments; comment only non-obvious
  security/design choices; secrets stay in env vars; no LangChain/CrewAI/agent
  frameworks; no new dependencies without explanation; no financial approval
  or payment logic.
- **S9 — README**: correct any inaccurate setup instructions found during the
  slice.
- **S10 — Git/validation**: report intended files + plan before editing;
  inspect the complete diff; check for accidental secrets and unrelated
  changes; run `manage.py check`, migration checks, and the complete existing
  backend test suite; report PASS/FAIL/NOT VERIFIED. Do not commit or stage
  automatically; do not modify `.env` (or blocked env files) without explicit
  authorization.

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S8 | Create `apps/organizations` and `apps/accounts`; add `rest_framework.authtoken` and both apps to `INSTALLED_APPS`; add REST_FRAMEWORK auth/permission defaults | done |
| T2 | S1,S2,S3,S7 | Models `Organization`, `OrganizationMembership` + role choices + unique constraint; migration `0001_initial` | done |
| T3 | S4,S5 | `IsActiveOrganizationMember` permission; serializers; `OrganizationViewSet`; router under `/api/v1/`; wire `config/urls.py` | done |
| T4 | S4,S5 | `apps/accounts`: `GET /api/v1/auth/me/` safe-profile endpoint with memberships and roles | done |
| T5 | S6 | Integration tests for organizations API + auth/me (real token auth; all 11 required cases) | done |
| T6 | S9 | Correct README inaccuracies; align documented API prefix; append change-log row in implementation contract | done |
| T7 | S10 | Validation: makemigrations/migrate/check, full backend suite, diff + secret review, completion report | done |

Commits: the orchestrator contract calls for work-unit commits, but the user
explicitly instructed "Do not commit automatically. Do not stage files
automatically." — user instruction wins; no commits or staging this slice.

## Log

- **L1 (verbatim, truncated for storage)**: "PayBlood — Phase 2, Slice 1:
  Organizations and Tenant-Scoped Authentication. Implement the first
  functional slice of Phase 2 using the existing repository and implementation
  contract. … mandatory preflight … scope … domain model … security
  invariants … API baseline … testing requirements … database and migrations …
  implementation quality … git and validation workflow … completion report …
  Stop after this slice and wait for review."
- L2: Design decisions (from parent): keep Django's default `auth.User`
  (already migrated, no project models depend on it; contract says use the
  existing user model and do not change `AUTH_USER_MODEL` casually) — no
  migration-breaking change. Auth baseline: DRF `TokenAuthentication` +
  `SessionAuthentication` (Phase 1 provides no login; login/registration
  deferred to a later slice; tests authenticate with real tokens). Inaccessible
  organizations return uniform 404 (HidingByNotExisting) to avoid disclosing
  existence; active membership of an active organization is the access gate;
  roles are data now, no per-role gating yet. `/auth/me/` exposes identity and
  active memberships only (no staff/superuser flags, no tokens).

- L3: URL double-prefix bug (router 'organizations' included at
  'api/v1/organizations/') found by the test suite (list hit the router
  API-root view; detail paths 404'd). Fixed by including the router at
  'api/v1/'. All 24 tests green afterwards; README/contract/environments
  corrections applied (T6).
