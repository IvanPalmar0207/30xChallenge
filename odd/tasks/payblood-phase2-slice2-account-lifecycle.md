# PayBlood — Phase 2, Slice 2: Account Lifecycle and Membership Administration

Reference: `docs/implementation-contract.md` (unchanged invariants); Slice 1 ODD spec
(`odd/tasks/payblood-phase2-slice1-organizations-auth.md`).

## Specs

- **S1 — Scope**: only (1) safe admin-created user accounts, (2) membership creation/management,
  (3) org-scoped role assignment, (4) user/membership activation/deactivation, (5) server-side
  authorization, (6) audit records for security-relevant admin changes, (7) tests + docs. NOT in
  scope: public registration, password reset email flows, invitations, MFA, frontend admin screens,
  vendors, invoices, extraction, policies, financial decisions, payments. No new dependencies
  without explanation.
- **S2 — Account lifecycle**: reuse default Django user model (do not change `AUTH_USER_MODEL`).
  Admin creates users: validate/normalize email; Django password hashing APIs; never store
  plaintext; never hardcode passwords; never expose passwords/hashes/tokens/secrets in responses
  or logs; no public self-registration; client can never set `is_superuser`/`is_staff`/global
  permissions/roles outside the server-side workflow. "Prefer an unusable password until a
  separately designed credential setup flow exists if that fits the current authentication
  requirements." Deactivate/reactivate via Django's active-state mechanism; a deactivated account
  must not authenticate or access protected endpoints (verify with existing auth classes + tests).
- **S3 — Membership management**: list memberships for an org the actor administers; create for an
  existing user; assign one of `FINANCE_ADMIN`, `OPERATOR`, `APPROVER`, `AUDITOR`; change role;
  deactivate/reactivate without deleting history; prevent duplicates (handle uniqueness cleanly);
  inactive memberships grant nothing; no membership creation for inactive orgs; never trust
  client-chosen org IDs (resolve actor authority server-side per operation); a role in one org
  grants nothing in another.
- **S4 — Authorization**: only an authorized `FINANCE_ADMIN` of an ACTIVE org manages ordinary users
  and memberships in that org. Admins must not create/promote global superadmin/staff. Prevent
  self-promotion to a higher role. "Prevent an administrator from granting a role that exceeds
  their own authority. In particular, a `FINANCE_ADMIN` must not be able to grant `FINANCE_ADMIN`
  to another user unless an explicit existing contract and permission model authorizes this. If no
  such delegation rule exists, deny it by default and explain the limitation." Admins must not
  deactivate/modify global superadmin accounts via org endpoints. No approval authority inferred
  from staff/superuser. Separation of duties: account administration does not grant invoice
  approval authority. Every endpoint checks permissions server-side; no frontend reliance;
  consistent authorization behavior (no leaking other orgs' data).
- **S5 — Authentication**: inspect Token + Session setup; document intended auth for write
  endpoints; preserve CSRF for session-authenticated unsafe requests; do not disable CSRF globally;
  test actual auth classes and ensure inactive users are rejected; do not claim token-only if
  session auth is still enabled; never return credentials/tokens from account-management endpoints.
  Do not redesign the whole auth system.
- **S6 — Audit trail**: minimum capability for account/membership administration. Events: account
  created; account activated/deactivated; membership created; membership role changed; membership
  activated/deactivated. Include actor, org context when applicable, action, target reference,
  timestamp, safe metadata. Never log passwords/hashes/tokens/secret keys/raw auth headers. Do not
  expose audit records of other orgs to unauthorized users. Prevent ordinary API users from
  modifying/deleting audit events. If append-only is claimed, verify application-level enforcement
  and document DB-level limitation. Audit records must persist consistently with the change: never
  report success if the required audit record failed to persist.
- **S7 — API**: follow `/api/v1/` conventions; DRF serializers/permissions/status codes. Example
  endpoints (inspect first, use consistent design): `GET/POST
  /api/v1/organizations/{id}/memberships/`, `PATCH
  /api/v1/organizations/{id}/memberships/{membership_id}/`, an authorized account-creation endpoint
  scoped to an org, a narrowly scoped account activation/deactivation endpoint. Explicit
  serializers whitelisting writable fields; never bind sensitive model fields from arbitrary JSON.
  Transactions where change + audit must succeed/fail together. Handle duplicates and invalid
  state transitions predictably.
- **S8 — Required tests** (at least): (1) anonymous cannot create accounts/memberships; (2) operator
  cannot manage memberships; (3) auditor cannot manage memberships; (4) authorized FINANCE_ADMIN
  performs only permitted operations; (5) org A admin cannot manage org B; (6) inactive orgs reject
  membership management; (7) inactive users cannot authenticate/access; (8) inactive memberships
  cannot authorize; (9) client cannot grant staff/superuser; (10) FINANCE_ADMIN cannot self-promote
  or grant beyond authority; (11) role change takes effect on next request; (12) duplicate
  memberships rejected safely; (13) account deactivation preserves history; (14) passwords and
  credentials never in responses or audit metadata; (15) audit records created for successful
  changes; (16) failed audited operation leaves no partial change; (17) session-authenticated
  unsafe requests preserve CSRF; (18) token-authenticated requests reject inactive users; (19) UUID
  and invalid-input errors without unhandled 500s; (20) Slice 1 isolation tests still pass. Real
  API requests; no mocks that bypass the logic under test.
- **S9 — DB/migrations**: migrations only if required by real model changes; never delete/reset
  existing migrations or DBs; do not change `AUTH_USER_MODEL`; verify model/migration consistency;
  PostgreSQL NOT VERIFIED unless actually tested; preserve existing records and constraints.
- **S10 — Git/validation**: keep changes limited to this slice; inspect final diff for unrelated
  changes and secrets; run Django system checks, migration consistency checks, relevant tests, and
  the full backend suite; report exact commands, exit codes, test counts; do not stage/commit/push
  automatically; do not edit blocked env files without authorization.

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S6,S9 | `AuditEvent` model (append-only app-level, PROTECT FKs, org context, JSON metadata) + migration `0002` | done |
| T2 | S4,S7 | `IsActiveOrganizationFinanceAdmin` permission (404 uniform for non-admins) + serializers (membership list/create/update, user create/activation; whitelisted fields; grantable roles) | done |
| T3 | S3,S4,S7 | Membership views (`GET/POST .../memberships/`, `GET/PATCH .../memberships/{id}/`) + nested URLs with `<uuid:>` converters | done |
| T4 | S2,S4,S7 | Account views (`POST .../users/` create user+membership atomically with unusable password; `PATCH .../users/{id}/` activate/deactivate) + URLs | done |
| T5 | S8 | Tests: membership management (roles, cross-org, inactive org, duplicates, self/superuser rules, role-change effect, malformed UUID) | done |
| T6 | S8 | Tests: account lifecycle (creation, email normalization, no staff/superuser, deactivation/reactivation, inactive-user auth rejection, CSRF, token inactive rejection, no secrets) | done |
| T7 | S8,S6 | Tests: audit events + transactional rollback (failed audit leaves no partial change) | done |
| T8 | S10 | Docs: README endpoints + test count (fix stale 24), contract changelog row | done |
| T9 | S10 | Validation: `manage.py check`, `makemigrations --check`, full backend suite; diff + secret review; completion report | done |

## Log

- L1: user request verbatim (abbreviated): "PayBlood — Phase 2, Slice 2: Account Lifecycle and
  Membership Administration. Implement the next incremental backend slice using the existing
  repository, implementation contract, and the completed Phase 2, Slice 1. … Mandatory preflight …
  Scope … Account lifecycle … Organization membership management … Authorization and privilege
  escalation … Authentication behavior … Audit trail … API and validation … Required automated
  tests … Database and migrations … Git and validation workflow … Completion report … Stop after
  completing this slice. Wait for review before proceeding."
- L2 (design decisions, parent): email normalized (strip + lowercase) doubles as username (no
  separate username field; uniqueness via email). Initial password = unusable
  (`set_unusable_password`); documented limitation: no credential setup flow yet. FINANCE_ADMIN is
  NOT grantable via the API (no delegation rule exists → deny by default; only OPERATOR/APPROVER/
  AUDITOR grantable). An admin cannot modify their own membership (prevents self-promotion and
  self-lockout). Superuser targets cannot be modified/deactivated via org endpoints. 404 uniform
  for org-level denial (not admin of that org — HidingByNotExisting, consistent with Slice 1); 403
  for within-org rule violations (self, superuser target, FINANCE_ADMIN grant). Account creation
  creates user + membership atomically (two audit events). `AuditEvent` lives in the organizations
  app (org-context audit; a future cross-domain audit app could move it); recording-only, read-only
  Django admin, no API read endpoint this slice. New nested routes use `<uuid:>` converters so
  malformed UUIDs 404 at routing. CSRF untouched; session-authenticated unsafe requests keep
  enforcement (tested with `enforce_csrf_checks=True`).

- L3 (implementation finds, tests): the default `auth.User` uses an INTEGER primary key, so the
  account-detail route uses `<int:pk>` — not `<uuid:pk>` like memberships (UUID PKs). The tests
  caught the initial mis-wiring (routing-level `HttpResponseNotFound` on every `users/{id}/`
  PATCH); fixed in `apps/organizations/urls.py`. Rollback tests use
  `APIClient(raise_request_exception=False)` because the default test client re-raises server
  exceptions instead of returning 500 responses.

- L4 (validation): `manage.py check` OK (exit 0), `makemigrations --check` clean, full backend
  suite **72 tests OK (exit 0)** — 25 slice-1 (incl. malformed-UUID regression) + 47 slice-2
  (26 membership + 21 accounts). No commits/staging per standing user instruction (work-unit
  commits deferred to user review).
