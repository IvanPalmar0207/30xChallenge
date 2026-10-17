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
`APPROVER` / `AUDITOR` are grantable). Login and token issuance are not
implemented yet.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/organizations/` | Organizations the authenticated user can access |
| GET | `/api/v1/organizations/{id}/` | One accessible organization (uniform 404 otherwise) |
| GET | `/api/v1/auth/me/` | Safe profile + active memberships with roles |
| GET | `/api/v1/organizations/{id}/memberships/` | Memberships of the organization (FINANCE_ADMIN only) |
| POST | `/api/v1/organizations/{id}/memberships/` | Create a membership for an existing user (FINANCE_ADMIN only) |
| GET / PATCH | `/api/v1/organizations/{id}/memberships/{membership_id}/` | Read; change role or active state (FINANCE_ADMIN only) |
| POST | `/api/v1/organizations/{id}/users/` | Create an account + first membership; unusable initial password (FINANCE_ADMIN only) |
| PATCH | `/api/v1/organizations/{id}/users/{user_id}/` | Activate / deactivate an account (FINANCE_ADMIN only) |

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
  72 integration tests in total (25 slice 1 + 47 slice 2).

**Not implemented yet (planned phases)** — public login/registration and
password setup or reset flows (created accounts hold an unusable password);
an audit read/export API (records exist but only the admin can browse them);
vendor and invoice models; AI invoice extraction; the deterministic policy
engine; the approval workflow; frontend administration UI. No placeholder
business logic has been added; domain apps land under `backend/apps/` and
feature modules under `frontend/src/app/features/` as they are built.

**Known limitations** — the only confirmed database is local SQLite
(PostgreSQL is pre-configured but untested); created accounts cannot log in
until a password-setup flow exists; `FINANCE_ADMIN` cannot be granted through
the API (no delegation rule); audit append-only is enforced at the
application level, not by the database; the Django admin is the default
scaffold.
