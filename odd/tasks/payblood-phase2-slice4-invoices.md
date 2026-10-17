# PayBlood — Phase 2, Slice 4: Invoice Management

Reference: `docs/implementation-contract.md` (unchanged invariants); slices 1-3 ODD specs.

## Specs

- **S1 — Scope**: register and query organization-scoped invoices linked to a
  vendor. NOT in scope: update/delete, OCR/AI extraction, file upload,
  purchase-order comparison, policy evaluation, approval/blocking/escalation,
  payments, frontend.
- **S2 — Invoice model**: UUID PK; organization FK (CASCADE); vendor FK
  (`on_delete=PROTECT`); invoice_number (normalized `strip().upper()`,
  documented: constraint acts on the stored value, normalization is
  application-level); issue_date required; due_date optional and not earlier
  than issue_date; amount `Decimal` strictly > 0, max 14 digits / 2 decimals
  (Django precision conventions); currency 3-letter code from the curated
  `SUPPORTED_CURRENCIES` list (USD, EUR, GBP, COP, MXN, ARS, BRL, PEN, CLP,
  CHF, CAD, JPY), normalized to uppercase; optional description; initial
  status `received` assigned server-side, never client-writable; created/
  updated timestamps.
- **S3 — Uniqueness**: DB-level `UniqueConstraint(organization, vendor,
  invoice_number)`; duplicate only for the same combination; same number from
  a different vendor in the same org, or from the same vendor in a different
  org, is allowed; `IntegrityError` captured → controlled 400 (race backstop).
- **S4 — Permissions**: reads (list/retrieve) for any ACTIVE member of the
  ACTIVE organization; creation for FINANCE_ADMIN and OPERATOR only (new
  `IsActiveOrganizationInvoiceCreator`); APPROVER/AUDITOR never gain creation
  by implication; staff/superuser confers no org-level rights; inactive
  users/memberships/organizations rejected; strict org isolation on every
  query; uniform 404 for inaccessible resources.
- **S5 — Vendor rules**: the vendor must belong to the URL organization — if it
  does not belong or does not exist → uniform 404; if it is inactive → 400
  `Vendor is inactive.`; client cannot assign organization/status/audit
  fields (whitelist: vendor, invoice_number, issue_date, due_date, amount,
  currency, description).
- **S6 — Audit**: new `invoice_created` action; actor, org, action, target,
  timestamp, safe metadata (`invoice_number`, `vendor`, `amount`, `currency`
  — never the full body, no secrets); creation + audit in one
  `transaction.atomic()`; audit failure rolls back the whole creation; no
  alternate mutation paths (Invoice admin registered read-only).
- **S7 — DB/migrations**: only the required migration; preserve all previous
  migrations/records; PostgreSQL NOT VERIFIED unless tested; isolated test DB.
- **S8 — Tests**: anonymous denied; FINANCE_ADMIN and OPERATOR create;
  APPROVER/AUDITOR cannot; reads for any active member; cross-org isolation
  (read + create); inactive org/membership/user; vendor nonexistent (404),
  cross-org (404), inactive (400); duplicates + normalization; DB-level
  uniqueness; invalid amount/currency/dates; protected-field injection;
  audit + rollback; malformed UUIDs; full-suite regression.
- **S9 — Docs**: README (endpoints, Invoices section, normalization, currency,
  uniqueness, audit, test counts), contract changelog row, ODD spec (no
  mirror — per user instruction to avoid duplicate artifacts).
- **S10 — Validation**: full suite isolated, `check`, `makemigrations
  --check`, final diff + secret review, exact results; no stage/commit/push.

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S2,S3,S7 | `Invoice` model (UUID, org FK CASCADE, vendor FK PROTECT, normalized invoice_number, dates, Decimal amount, currency, description, status received) + `INVOICE_CREATED` action + migration `0004` | done |
| T2 | S4,S5 | `IsActiveOrganizationInvoiceCreator` permission + invoice serializers (list/detail, create whitelist, normalization, currency list, amount/date validation, duplicate pre-check) | done |
| T3 | S4,S5,S6 | Invoice views (list/create with per-method permissions + vendor 404 pre-check, detail retrieve) + 2 routes + read-only admin | done |
| T4 | S8 | `tests_invoices.py` (37 tests covering all required cases) | done |
| T5 | S9 | README (endpoints, Invoices section, counts) + contract changelog row + ODD log | done |
| T6 | S10 | Validation: check, makemigrations --check, full suite isolated, diff + secret review, report | done |

## Log

- L1: user request verbatim (abbreviated): "PayBlood — Phase 2, Slice 4:
  Invoice Management. Fase inicial: inspección y especificación. … No
  implementes código todavía." (specification turn).
- L2 (user-confirmed technical contract, verbatim decisions): (1) DB-level
  uniqueness by `(organization, vendor, invoice_number)`; duplicate only for
  the same combination; IntegrityError → controlled 400. (2) invoice_number
  normalization `strip().upper()`; document that the constraint acts on the
  stored value and normalization happens in the application. (3)
  `SUPPORTED_CURRENCIES` curated: USD, EUR, GBP, COP, MXN, ARS, BRL, PEN,
  CLP, CHF, CAD, JPY; serializer validation + uppercase normalization. (4)
  Decimal amount strictly > 0, max 14 digits / 2 decimals, Django precision
  conventions. (5) issue_date required; due_date optional and not earlier
  than issue_date. (6) Initial status `received`, server-assigned, not
  client-modifiable. (7) Vendor must belong to the URL organization: not
  belonging or nonexistent → uniform 404; inactive → 400 `Vendor is
  inactive.` (8) `Invoice.vendor` uses `on_delete=PROTECT`. No update/delete,
  OCR, AI, policy evaluation, approvals, or payments. No stage/commit/push.
- L3 (implementation): 37 invoice tests green; full suite 149 OK, exit 0;
  `check` and `makemigrations --check` clean; migration `0004` applied;
  README + contract changelog updated; no mirror created (per user
  instruction).
