# PayBlood — Implementation Contract

> Agreed high-level architecture and implementation invariants for the PayBlood
> MVP (invoice processing and accounts-payable decision support). This document
> is binding for all future phases; changes to the invariants require an
> explicit agreement and a Log entry documenting the change.

## 1. Purpose and scope of the MVP

PayBlood is a hackathon MVP that ingests invoices, extracts structured invoice
data, and produces **decision support** for accounts payable. The system never
executes payments, never makes autonomous financial decisions, and treats
approval as a human-audited action supported by deterministic rules.

Out of scope for the MVP: real payment execution, banking integrations,
multi-currency treasury features, and full enterprise workflow tooling.

## 2. High-level architecture

- **Frontend** — Angular + TypeScript. Four module areas under `frontend/src/app/`:
  - `core/` — singleton services, guards, API client, app-wide configuration.
  - `shared/` — reusable components, pipes, directives, typed DTOs.
  - `features/` — one directory per feature (auth, invoices, approvals, …).
  - `public/` — landing and unauthenticated pages.
- **Backend** — Python + Django + Django REST Framework. Django project under
  `backend/config/`; business domain lives in isolated Django apps under
  `backend/apps/`; repository-level tests live under `backend/tests/`.
  Future domain apps: `organizations`, `accounts`, `vendors`, `invoices`,
  `extraction`, `policies`, `approvals`, `audit`.
- **Database** — SQLite for local development; PostgreSQL stays possible by
  switching `DATABASE_URL` in the environment. All credentials come from the
  environment, never from code.

## 3. Implementation invariants

1. **The AI extracts invoice information; it does not approve invoices.**
   The extraction module transcribes and structures invoice data. It holds no
   approval authority and cannot change approval state.

2. **The deterministic backend policy engine owns financial decisions.**
   Any approval, rejection, or flag is computed by deterministic, versioned,
   server-side rules over validated data. No client-side or generative logic
   participates in a decision.

3. **Failures and ambiguous critical data must never result in automatic
   approval.**
   Missing, malformed, or conflicting critical fields (amount, vendor, due
   date, invoice number) force a non-approval outcome: explicit review or
   rejection. Fail-closed is the default for every decision path.

4. **No real payments are executed.**
   The MVP produces verdicts and audit records only. There is no payment
   provider integration, no money movement, and no payment authorization
   endpoint.

5. **Organization isolation and server-side authorization are mandatory.**
   Every request is scoped server-side to the authenticated user's
   organization. The client never decides what data it may read; missing or
   invalid authorization is a denial.

6. **Financial decisions must be auditable and linked to a policy version.**
   Every stored decision references the exact policy version that produced it,
   with the inputs and the rule trace retained. Policy versions are immutable
   once used in a decision.

7. **Secrets must never be committed.**
   `.env`, databases, credentials, keys, and AI API keys are gitignored.
   Only `.env.example` with safe placeholders is tracked. Frontend
   configuration is public by design and contains no secrets.

8. **Changes must be modular, tested, and committed incrementally.**
   Work lands in small, reviewable units with tests and documentation beside
   the behavior, using Conventional Commits (e.g.
   `feat(policies): implement deterministic invoice evaluation`).

## 4. Conventions

- English identifiers, comments, and technical documentation.
- Comments only where they explain non-obvious decisions, security invariants,
  or important constraints.
- No business logic in `views.py`, Angular components, or configuration files;
  logic lives in testable services and domain applications.
- No placeholder business logic or fake implementations: scaffolding only until
  its phase implements real behavior.
- Forbidden: hardcoded secrets in source, fixtures, docs, or frontend config.
- Decisions that require a policy rule are specified explicitly before
  implementation; undocumented rules and financial thresholds are never
  invented.

## 5. Document change log

| Date | Change |
| --- | --- |
| 2026-10-16 | Initial contract agreed for Phase 1 (repository foundation). |
| 2026-10-17 | Phase 2, slice 1: tenant-scoped authentication baseline (organizations, memberships, roles, `/api/v1/` endpoints). Invariants unchanged. |
| 2026-10-17 | Phase 2, slice 2: account lifecycle and membership administration (admin-created users, memberships, role assignment, activation, transactional audit trail). Invariants unchanged. |
