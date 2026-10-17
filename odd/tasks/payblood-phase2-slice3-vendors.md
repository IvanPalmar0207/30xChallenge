# PayBlood — Phase 2, Slice 3: Vendor Management

Reference: `docs/implementation-contract.md` (unchanged invariants); slices 1-2 ODD specs.

## Specs

- **S1 — Scope**: only organization-scoped vendor management: (1) vendor data model + migration,
  (2) creation and listing, (3) detail and controlled updates, (4) activation/deactivation,
  (5) organization-level authorization and tenant isolation, (6) audit events for successful admin
  changes, (7) tests and docs. NOT in scope: invoices, extraction, AI, purchase orders, payments,
  budgets, frontend screens, integrations, unrelated auth changes.
- **S2 — Vendor model**: UUID PK; organization ownership FK (exactly one org; ownership never from
  client); legal name; tax identifier (conservative normalization, jurisdiction-agnostic,
  documented); active/inactive status; created/updated timestamps. DB-level uniqueness of tax_id
  within an organization; same tax_id allowed across organizations; identifiers normalized before
  uniqueness checks; controlled errors for missing/malformed/duplicate/invalid data (no 500); no
  delete-as-deactivation; no unsupported financial/compliance claims.
- **S3 — API**: organization-scoped endpoints under `/api/v1/organizations/{org}/vendors/...` with
  explicit writable-field allowlists; organization ownership never writable; cross-org access via
  known UUID prevented; uniform not-found behavior; consistent with previous slice conventions.
- **S4 — Authorization**: reads (list/retrieve) for any ACTIVE member of the ACTIVE organization;
  creation/update/activation/deactivation reserved for FINANCE_ADMIN of that org. OPERATOR /
  APPROVER / AUDITOR gain no mutation rights. Staff/superuser confers no org-level business
  permissions. Inactive users/memberships/organizations rejected. Org A never reads/mutates Org B
  vendors. Recheck permissions every request.
- **S5 — Activation**: deactivation preserves the record; inactive vendors remain distinguishable
  from nonexistent ones to authorized users; an ordinary update (PATCH) must NOT silently
  reactivate — status is not writable there; activation/deactivation are explicit operations with
  permission + audit; no invoice-blocking/payment claims (later slice).
- **S6 — Audit**: reuse `AuditEvent`; record vendor_created / vendor_updated (only real business
  changes) / vendor_activated / vendor_deactivated; actor, org, action, target, timestamp, safe
  metadata; never credentials/tokens/headers/full request body; change + event atomic (rollback on
  audit failure); no alternate mutation paths (Vendor admin registered read-only); append-only
  stays application-level (documented limitation).
- **S7 — DB/migrations**: only the migration required; preserve all migrations/records; uniqueness
  constraint IN THE DATABASE; handle uniqueness violations safely (no 500 on races); keep
  compatible with supported DB config; PostgreSQL NOT VERIFIED unless tested; isolated test DB.
- **S8 — Tests** (at least): anonymous denied; FINANCE_ADMIN creates; reads per policy; OPERATOR/
  APPROVER/AUDITOR cannot mutate; cross-org read+mutate blocked; inactive org; inactive membership;
  inactive user; org assignment injection blocked; staff/superuser no bypass; duplicate tax_id in
  org rejected; same tax_id across orgs allowed; normalization consistent; invalid/missing fields
  controlled; deactivate without delete; no silent reactivation via ordinary update; activate/
  deactivate permission-gated; field injection blocked; audit events recorded; metadata safe;
  audit-failure rollback; malformed UUIDs no 500; slice 1+2 regressions green.
- **S9 — Docs**: README (model, endpoints+roles, normalization rules, activation behavior, audit
  guarantees/limitations, test commands+counts, deferred items) and contract changelog row; ODD
  spec + mirror following the established convention.
- **S10 — Validation**: final diff review incl. untracked; Django system checks; migration
  consistency; vendor tests + full backend suite (isolated DB); exact commands/exit codes/counts;
  secret/artifact scan; exact Git status; no stage/commit/push; no blocked env edits. Stop after
  slice; wait for review.

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S2,S7 | `Vendor` model (UUID, org FK CASCADE, legal_name, normalized tax_id, status, timestamps, DB UniqueConstraint(organization, tax_id)) + 4 new `AuditEvent.Action`s + migration `0003` | done |
| T2 | S4 | `IsActiveOrganizationMemberInUrl` read permission + vendor serializers (list/detail, create whitelist, update whitelist no-status, normalization `strip().upper()`, duplicate pre-check with self-exclusion) | done |
| T3 | S3,S4,S5 | Vendor views (list/create with per-method permissions, detail retrieve/update, activate/deactivate explicit) + 4 routes with `<uuid:>` converters | done |
| T4 | S6 | Vendor admin registered read-only (no alternate mutation path) | done |
| T5 | S8 | `tests_vendors.py` (40 tests covering all required cases) | done |
| T6 | S9 | README (endpoints, normalization, status, counts) + contract changelog row | done |
| T7 | S10 | Validation: check, makemigrations --check, full suite isolated, diff + secret review, report | done |

## Log

- L1: user request verbatim (abbreviated): "PayBlood — Phase 2, Slice 3: Vendor Management.
  Implement the next incremental backend slice: organization-scoped vendor management. … (scope,
  data model, API endpoints, authorization and tenant isolation, activation/deactivation, audit
  trail, database and migration safety, required automated tests, documentation, validation and
  Git discipline, completion report) … Stop after completing this slice. Do not begin invoice
  management or AI extraction until this slice has been reviewed and explicitly accepted."
- L2 (user-approved design decisions): (1) reads for any ACTIVE member of the ACTIVE org
  (list/retrieve); mutations FINANCE_ADMIN only. (2) Explicit `activate/` and `deactivate/`
  endpoints; ordinary PATCH never touches status. (3) `on_delete=CASCADE` for Vendor org relation
  (consistent with memberships; no org deletion via API; no vendor deletion — deactivation only).
  (4) tax_id normalization = `strip()` + `upper()` only (no removal of hyphens/internal spaces);
  uniqueness constraint per organization on the normalized value. No conflict with the
  implementation contract was found.
- L3 (test fix during implementation): the PATCH response uses the update serializer (only
  `legal_name`/`tax_id`), consistent with the Slice 2 membership PATCH convention; the
  no-silent-reactivation test was corrected to assert DB state instead of a `status` key in the
  PATCH response. 40 vendor tests green; full suite 112 OK, exit 0.
