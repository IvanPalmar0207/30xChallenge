# PayBlood

Hackathon MVP for **invoice processing and accounts-payable decision support**.
PayBlood ingests invoices, extracts structured data (AI-assisted), and produces
deterministic, auditable decision support for accounts payable. **The system
never executes payments, and the AI never approves invoices.**

> Architecture and invariants: [docs/implementation-contract.md](docs/implementation-contract.md)

## Technology stack (selected and pinned in Phase 1)

| Layer | Technology | Version |
| --- | --- | --- |
| Frontend | Angular (TypeScript) | 22.2.3 (TypeScript ~6.0.2) |
| Node.js runtime | Node / npm | v24.18.0 / 11.16.0 |
| Frontend tests | Vitest + jsdom | 5.0.5 |
| Backend | Python | 3.14.7 |
| Backend | Django / Django REST Framework | 6.1.2 / 3.18.3 |
| Backend extras | django-cors-headers, django-environ, psycopg | 4.9.0 / 0.14.0 / 3.3.6 |
| Database | SQLite (local default); PostgreSQL supported via `DATABASE_URL` | — |

Django 5.2 LTS does not support Python 3.14, so Django 6.1.x was selected for
the installed Python. All backend dependencies are pinned in
`backend/requirements/base.txt`; npm versions are locked by
`frontend/package-lock.json`.

## Repository structure

```
PayBlood/
├── backend/                 # Django project
│   ├── config/              #   project configuration (settings, urls, wsgi/asgi)
│   ├── apps/                #   future domain apps (organizations, invoices, …)
│   ├── tests/               #   repository-level test suites
│   ├── requirements/
│   │   ├── base.txt         #   pinned runtime dependencies
│   │   └── dev.txt          #   development-only additions
│   ├── manage.py
│   └── .venv/               # local virtual environment (gitignored)
├── frontend/                # Angular application
│   └── src/app/
│       ├── core/            #   singletons, guards, API client
│       ├── shared/          #   reusable components, pipes, DTOs
│       ├── features/        #   one directory per feature
│       └── public/          #   landing / unauthenticated pages
├── docs/
│   └── implementation-contract.md
├── .env.example             # tracked template with safe placeholders
├── .gitignore
└── README.md
```

## Local setup

Requirements: Python 3.14+, Node.js 24+ (with npm).

### 1. Environment variables

Copy the template and fill in real local values:

```bash
cp .env.example .env
```

Generate a real Django secret key and put it in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

The real `.env` is gitignored. Only `.env.example` (placeholders) is tracked.
See [Environment variables](#environment-variables) below.

### 2. Backend (Django + DRF)

```bash
cd backend
python -m venv .venv
# Windows:
.venv/Scripts/pip install -r requirements/dev.txt
# macOS/Linux:
# source .venv/bin/activate && pip install -r requirements/dev.txt

.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py runserver
# API and admin available at http://127.0.0.1:8000/ (admin at /admin/, API under /api/v1/)
```

### 3. Frontend (Angular)

```bash
cd frontend
npm install
npm start
# App served at http://localhost:4200/. The API base URL is a public build
# value in frontend/src/environments/*; CORS origins are configured in .env.
```

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django signing secret (required; no default) | — |
| `DJANGO_DEBUG` | Django debug flag | `true` (local dev) |
| `DJANGO_ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` |
| `DATABASE_URL` | SQLite or PostgreSQL URL | `sqlite:///db.sqlite3` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Browser origins allowed to call the API | `http://localhost:4200` |
| `AI_PROVIDER` / `AI_MODEL` / `AI_API_KEY` | Reserved for the AI extraction phase | empty |

Frontend build-time values (`frontend/src/environments/`) are **public** by
design and contain no secrets.

## API endpoints (v1)

All endpoints require authentication (DRF Token or session authentication).
The access gate for organizations is an ACTIVE membership in an ACTIVE
organization, resolved server-side. Any other case — unknown ID, inactive
membership, inactive organization, or another user's organization — returns
the same 404 and never discloses whether another organization exists.

Administration endpoints additionally require an ACTIVE `FINANCE_ADMIN`
membership in the URL organization; anyone else gets the same 404. Inside the
organization, forbidden operations return 403: modifying your own
membership, modifying global-superuser memberships, or granting
`FINANCE_ADMIN` (no delegation rule exists yet — only `OPERATOR` /
`APPROVER` / `AUDITOR` are grantable). Vendor reads (list/retrieve) are open
to any ACTIVE member of the ACTIVE organization; vendor creation, updates,
and activation/deactivation require `FINANCE_ADMIN` (anyone else gets the
same 404). Invoice reads are open to any active member; invoice creation
requires `FINANCE_ADMIN` or `OPERATOR` (anyone else gets the same 404).
Login is available at `/api/v1/auth/login/` (see Authentication below).

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/organizations/` | Organizations the authenticated user can access |
| GET | `/api/v1/organizations/{id}/` | One accessible organization (uniform 404 otherwise) |
| GET | `/api/v1/auth/me/` | Safe profile + active memberships with roles |
| POST | `/api/v1/auth/login/` | Exchange email + password for a DRF token (uniform 401, throttled) |
| POST | `/api/v1/auth/logout/` | Revoke the current token (or flush the session) |
| POST | `/api/v1/auth/set-password/` | Set the initial password with a one-time invitation token |
| POST | `/api/v1/organizations/{id}/users/{user_id}/invite/` | Issue a one-time password-setup token (FINANCE_ADMIN only) |
| GET | `/api/v1/organizations/{id}/memberships/` | Memberships of the organization (FINANCE_ADMIN only) |
| POST | `/api/v1/organizations/{id}/memberships/` | Create a membership for an existing user (FINANCE_ADMIN only) |
| GET / PATCH | `/api/v1/organizations/{id}/memberships/{membership_id}/` | Read; change role or active state (FINANCE_ADMIN only) |
| POST | `/api/v1/organizations/{id}/users/` | Create an account + first membership; unusable initial password (FINANCE_ADMIN only) |
| PATCH | `/api/v1/organizations/{id}/users/{user_id}/` | Activate / deactivate an account (FINANCE_ADMIN only) |
| GET | `/api/v1/organizations/{id}/vendors/` | List vendors of the organization, active and inactive (any active member) |
| POST | `/api/v1/organizations/{id}/vendors/` | Create a vendor (FINANCE_ADMIN only) |
| GET | `/api/v1/organizations/{id}/vendors/{vendor_id}/` | One vendor of the organization, active or inactive (any active member) |
| PATCH | `/api/v1/organizations/{id}/vendors/{vendor_id}/` | Update legal name or tax identifier (FINANCE_ADMIN only; never status) |
| POST | `/api/v1/organizations/{id}/vendors/{vendor_id}/activate/` | Explicitly activate a vendor (FINANCE_ADMIN only) |
| POST | `/api/v1/organizations/{id}/vendors/{vendor_id}/deactivate/` | Explicitly deactivate a vendor, preserving the record (FINANCE_ADMIN only) |
| GET | `/api/v1/organizations/{id}/invoices/` | List invoices of the organization (any active member) |
| POST | `/api/v1/organizations/{id}/invoices/` | Register an invoice (FINANCE_ADMIN or OPERATOR only) |
| GET | `/api/v1/organizations/{id}/invoices/{invoice_id}/` | One invoice of the organization (any active member) |
| GET | `/api/v1/organizations/{id}/policies/` | List policy versions (any active member) |
| POST | `/api/v1/organizations/{id}/policies/` | Create a new policy version, deactivating the previous one (FINANCE_ADMIN only) |
| GET | `/api/v1/organizations/{id}/policies/{policy_id}/` | One policy version (any active member) |
| POST | `/api/v1/organizations/{id}/invoices/{invoice_id}/evaluate/` | Evaluate an invoice against the active policy (FINANCE_ADMIN or OPERATOR trigger; the engine decides) |
| GET | `/api/v1/organizations/{id}/invoices/{invoice_id}/decision/` | Read the persisted decision for one invoice (any active member) |

## Invoices

Organization-scoped invoice registration and querying (Phase 2, slice 4). An
invoice belongs to exactly one organization (resolved from the URL, never
from the request body) and is linked to exactly one vendor of that
organization. Reads are open to any ACTIVE member of the ACTIVE organization;
creation requires an ACTIVE `FINANCE_ADMIN` or `OPERATOR` membership (uniform
404 for everyone else). There is no update or delete in this slice: the
initial status is always `received`, assigned server-side, and lifecycle
states (approval, blocking, escalation) arrive in later slices.

- **Invoice number** — normalized with `strip()` + `upper()` only (consistent
  with the tax-identifier convention). The normalized value is what gets
  stored, so the database uniqueness constraint operates on the stored value
  while normalization itself is an application-level guarantee (documented
  limitation).
- **Uniqueness** — one invoice number per (organization, vendor) at the
  database level: the same number from a different vendor in the same
  organization, or from the same vendor in a different organization, is
  allowed. Duplicate attempts answer a controlled 400.
- **Money and currency** — `amount` is a `Decimal` strictly greater than
  zero, max 14 digits / 2 decimals (never `float`). `currency` must be one of
  the curated supported codes: USD, EUR, GBP, COP, MXN, ARS, BRL, PEN, CLP,
  CHF, CAD, JPY (normalized to uppercase; the list is documented and can be
  extended deliberately).
- **Dates** — `issue_date` is required; `due_date` is optional and must not
  be earlier than the issue date.
- **Vendor rules** — the vendor must belong to the URL organization: a
  vendor that does not exist or belongs to another organization answers the
  same uniform 404; an inactive vendor answers a controlled 400
  (`Vendor is inactive.`).
- **Audit** — every successful creation records an `invoice_created` event
  with actor, organization, target, timestamp, and safe metadata
  (`invoice_number`, `vendor`, `amount`, `currency` — never the full request
  body, no secrets). The creation and its audit event commit in one
  transaction; a failed audit write rolls back the creation. The Django
  admin surface for invoices is read-only, so no un-audited mutation path
  exists.
- **No financial claims** — extraction, policy evaluation, approval,
  blocking, escalation, and payments are out of scope for this slice; the
  `received` status carries no financial effect yet.

## Authentication

Phase 2, slice 5. Accounts are created by an administrator with an unusable
password; the administrator then issues a one-time invitation token that the
user redeems to set their own initial password.

- **Login** — `POST /api/v1/auth/login/` with `{email, password}` returns
  `{token, user}` where `user` is a safe identity payload (no password, no
  staff/superuser flags). Wrong credentials and inactive accounts answer the
  same uniform 401 (`Invalid email or password.`), so the endpoint never
  discloses whether an email exists (no user enumeration). The email is
  normalized (strip + lowercase).
- **Invitation** — `POST /api/v1/organizations/{id}/users/{user_id}/invite/`
  (FINANCE_ADMIN only) returns a one-time setup token exactly once; only its
  SHA-256 hash is stored, it expires after 72 hours, and issuing a new one
  invalidates previous unused tokens. The admin relays the raw token
  out-of-band (in production this would be emailed).
- **Set password** — `POST /api/v1/auth/set-password/` with
  `{setup_token, password}` sets the initial password and marks the token
  used. An ordinary or filtered DRF access token is **never** accepted here,
  so a leaked access token cannot take over an account that has no password
  yet. Passwords are validated with Django's password validators.
- **Logout and revocation** — `POST /api/v1/auth/logout/` revokes the
  current token (or flushes the session for session-authenticated requests).
  DRF tokens do **not** expire automatically (documented limitation);
  deactivating an account invalidates its tokens immediately (401 on next
  use).
- **Throttling** — login and set-password are throttled at 30 attempts per
  minute per IP (DRF built-in throttling, no new dependency).
- **Audit** — `invitation_issued` (admin, org context) and `password_set`
  (the user, no org context) events are recorded with safe metadata; raw
  tokens, hashes, and passwords are never logged.

## Policy engine

Phase 2, slice 6. A versioned, immutable policy and a deterministic engine
decide whether an invoice is `approved` (simulation only), `blocked` (mandatory
rule violation), or `escalated` (human review / cannot decide safely). The
engine is the only decision authority: the requester never chooses the outcome,
and no endpoint accepts a decision field from the client.

- **Policy model** — each organization has at most one ACTIVE policy; creating
a new version deactivates the previous one inside the same transaction. Every
version is immutable once created: historical versions cannot be edited or
deleted through the API (read-only admin surface too).
- **Rules** — `allowed_currencies` restricts the invoice currency;
`max_amount` is a hard cap; `escalation_threshold` sends amounts above it to
human review; `require_due_date` / `require_description` escalate invoices with
missing data. Semantics are explicit: `allowed_currencies=[]` means **no
currency restriction** (documented so an ambiguous empty configuration can
never approve by accident). When both limits are set, `escalation_threshold`
must not exceed `max_amount` (coherence checked at creation, else 400).
- **Decision order (precedence)** — `blocked → escalated → approved`:
currency not allowed or `amount > max_amount` blocks; otherwise
`amount > escalation_threshold` or a required field missing escalates; only
when every rule passes does the invoice get `approved`. Comparisons are strict
(`>`): an amount exactly equal to a limit does not exceed it.
- **No active policy = escalated** — an invoice is never approved without a
valid, applicable policy (`no_active_policy`).
- **Decision record** — one persisted `PolicyDecision` per invoice (database
uniqueness constraint), with result, reason code, reason detail, policy id and
version, and an unambiguous `rules_snapshot` of the effective rules at
evaluation time: later policy changes never alter recorded decisions. The
requester never chooses the outcome.
- **State machine & transactions** — evaluation requires `status == received`
(any other state answers `409 Conflict`). The decision, the invoice status
transition, and the `invoice_evaluated` audit event commit in one transaction;
any failure rolls back everything and the API answers a generic `500` with no
internal details. Internal errors never approve and never leave partial state.
- **Concurrency** — the invoice row is locked with `select_for_update()` where
the database supports it (PostgreSQL), and the one-decision-per-invoice unique
constraint is the universal backstop. SQLite concurrency is not claimed as
validated (documented limitation).
- **Permissions** — policy reads and decision reads for any active member;
policy creation FINANCE_ADMIN only; evaluation is triggered by
FINANCE_ADMIN/OPERATOR (an operator never becomes a human approver). Unknown
organizations, inactive organizations, and unauthorized roles all resolve to
the same uniform 404.
- **Audit** — `invoice_evaluated` (result, reason_code, policy_version,
decision_id — no secrets, no full body) and `policy_created` (version,
is_active) events, recorded transactionally and append-only at the
application level.
- **No financial claims** — this is a simulation decision, not a payment:
no payments, budgets, or purchase orders exist.

## Vendors

Organization-scoped vendor management (Phase 2, slice 3). A vendor belongs to
exactly one organization (resolved from the URL, never from the request body)
and is never deleted: deactivation (status `inactive`) preserves the record
and its historical identity. Reads are open to any ACTIVE member of the ACTIVE
organization; creation, updates, and activation/deactivation require an ACTIVE
`FINANCE_ADMIN` membership (uniform 404 for everyone else).

- **Tax identifier** — normalized with `strip()` + `upper()` only (hyphens,
  internal spaces, and other characters are preserved; no country-specific
  format validation, because the supported jurisdiction is unspecified). The
  normalized value is what gets stored, so the database uniqueness constraint
  operates on it: one tax identifier per organization, and the same identifier
  is allowed in different organizations.
- **Activation** — explicit operations only. The ordinary `PATCH` accepts
  `legal_name` and `tax_id`; `status` is not writable there, so an inactive
  vendor is never silently reactivated. Both operations are idempotent and
  recorded in the audit trail in the same transaction as the change.
- **Audit** — `vendor_created`, `vendor_updated` (only when business data
  actually changed; metadata lists changed fields with from/to values, never
  the full request body), `vendor_activated`, and `vendor_deactivated` events
  with actor, organization, target, and timestamp. A failed audit write rolls
  back the mutation. Append-only remains enforced at the application level
  (the database itself does not enforce it). The Django admin surface for
  vendors is read-only, so no un-audited mutation path exists.
- **No financial claims** — vendor verification, invoice blocking, or payment
  decisions are out of scope for this slice; a vendor's `active`/`inactive`
  status carries no financial effect yet.

## Commands

| Task | Command |
| --- | --- |
| Django checks | `cd backend && .venv/Scripts/python manage.py check` |
| Run backend | `cd backend && .venv/Scripts/python manage.py runserver` |
| Backend tests | `cd backend && .venv/Scripts/python manage.py test` |
| Migrations | `cd backend && .venv/Scripts/python manage.py makemigrations <app>` |
| Run frontend | `cd frontend && npm start` |
| Frontend build | `cd frontend && npm run build` |
| Frontend tests | `cd frontend && npm test` |

## Security notes

- Secrets live only in the gitignored `.env`; the repository tracks only the
  placeholder template. Never commit `.env`, databases, uploads, logs, or
  credentials.
- Django refuses to start without `DJANGO_SECRET_KEY`, so a placeholder cannot
  silently become the app secret.
- Frontend configuration is public: never put API keys or credentials in
  `src/environments/` or any frontend file.
- CORS is restricted to configured origins; the API is not public.
- Decision invariants (AI never approves, fail-closed policy engine, no real
  payments, organization isolation, auditable decisions) are binding — see
  [docs/implementation-contract.md](docs/implementation-contract.md).

## Implementation status (Phase 1)

**Done** —
- (Phase 1) repository foundation.
- (Phase 2, slice 1) tenant-scoped authentication baseline: `Organization`
  and `OrganizationMembership` models with a database-level (user,
  organization) uniqueness constraint, seeded organization roles
  (`FINANCE_ADMIN` / `OPERATOR` / `APPROVER` / `AUDITOR`), server-side
  active-membership authorization with uniform 404 behavior, DRF Token +
  session authentication baseline, `/api/v1/organizations/`,
  `/api/v1/organizations/{id}/`, `/api/v1/auth/me/`.
- (Phase 2, slice 2) account lifecycle and membership administration:
  administrator-created accounts (email normalized to the username, unusable
  initial password), membership create / role change / activate-deactivate
  under FINANCE_ADMIN-only server-side authorization (uniform 404 for
  non-admins, 403 for self-modification or superuser targets, no
  `FINANCE_ADMIN` delegation), and an append-only `AuditEvent` trail recorded
  transactionally with every change (read-only in the Django admin).
- (Phase 2, slice 3) organization-scoped vendor management: `Vendor` model
  owned by exactly one organization with a database-level (organization, tax
  identifier) uniqueness constraint and conservative strip+uppercase tax
  identifier normalization; reads for any active member; create/update/
  activate/deactivate reserved for FINANCE_ADMIN (uniform 404); explicit
  `activate/` / `deactivate/` operations (the ordinary PATCH never touches
  status); transactional audit events (`vendor_created`, `vendor_updated`,
  `vendor_activated`, `vendor_deactivated`); read-only vendor admin surface.
- (Phase 2, slice 4) organization-scoped invoice registration and querying:
  `Invoice` model owned by one organization and linked to one vendor of that
  organization (PROTECT FK), database-level (organization, vendor, invoice
  number) uniqueness with conservative strip+uppercase normalization, Decimal
  amount with curated currency codes, server-assigned `received` status,
  reads for any active member, creation for FINANCE_ADMIN/OPERATOR (uniform
  404), transactional `invoice_created` audit events, read-only invoice admin
  surface.
- (Phase 2, slice 5) secure login: `POST /api/v1/auth/login/` (uniform 401,
  no user enumeration, throttled), `POST /api/v1/auth/logout/` (revokes the
  current token), a one-time invitation flow
  (`.../users/{id}/invite/` + `POST /api/v1/auth/set-password/`) that stores
  only a SHA-256 hash of the setup token and never accepts an access token,
  and `password_set` / `invitation_issued` audit events.
- (Phase 2, slice 6) deterministic invoice policy engine: versioned immutable
  `Policy` (one active per organization), `evaluate_invoice` with strict
  comparisons and `blocked → escalated → approved` precedence, escalated
  `no_active_policy` fail-safe, persisted one-per-invoice `PolicyDecision`
  with an unambiguous rules snapshot, received → approved/blocked/escalated
  state machine with 409 on repeated evaluation, transactional
  decision + status + `invoice_evaluated`/`policy_created` audit events,
  `select_for_update()` + unique constraint against concurrency, and policy/
  decision reads for any active member with FINANCE_ADMIN-only policy
  creation.
  210 integration tests in total (25 slice 1 + 47 slice 2 + 40 slice 3 + 37 slice 4 + 27 slice 5 + 34 slice 6).

**Not implemented yet (planned phases)** — public self-registration and
password reset flows (initial passwords are set via the invitation flow;
forgotten-password reset is deferred); an audit read/export API (records
exist but only the admin can browse them); the human approval workflow on
top of `escalated` invoices, payments, and budgets/POs; AI invoice
extraction; the frontend administration UI. No placeholder
business logic has been added; domain apps land under `backend/apps/` and
feature modules under `frontend/src/app/features/` as they are built.

**Known limitations** — the only confirmed database is local SQLite
(PostgreSQL is pre-configured but untested; `select_for_update()` evaluation
concurrency is therefore not validated on the confirmed database); DRF tokens do not expire
automatically (logout or account deactivation is the revocation path);
forgotten-password reset and self-registration are deferred; `FINANCE_ADMIN`
cannot be granted through
the API (no delegation rule); audit append-only is enforced at the
application level, not by the database; the Django admin is the default
scaffold.
