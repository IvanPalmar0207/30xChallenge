# PayBlood — Phase 2, Slice 5: Secure Login

Reference: `docs/implementation-contract.md` (unchanged invariants); slices 1-4 ODD specs.

## Specs

- **S1 — Scope**: enable secure login with the existing DRF Token +
  SessionAuthentication baseline. NO new dependencies (no SimpleJWT). NO
  simulated token expiration. NO weakening of existing org permissions.
- **S2 — Login**: `POST /api/v1/auth/login/` accepts `{email, password}`
  (email normalized strip+lower); success → 200 `{token, user:{id, username,
  email, first_name, last_name}}` (no password, no staff flags, no secrets);
  failure → uniform 401 `Invalid email or password.` for wrong credentials
  AND inactive accounts (no user enumeration); anonymous throttle.
- **S3 — Logout**: `POST /api/v1/auth/logout/` (authenticated) revokes the
  current token (or flushes the session for session auth) → 204. DRF tokens
  do not expire automatically (documented); deactivation invalidates access
  immediately (existing behavior, preserved).
- **S4 — Initial password setup**: one-time invitation flow. FINANCE_ADMIN
  issues a setup token via `POST /api/v1/organizations/{org}/users/{id}/invite/`
  (invalidates previous unused tokens; returns the raw token once; only its
  SHA-256 hash is stored; 72h TTL). `POST /api/v1/auth/set-password/` accepts
  `{setup_token, password}` → sets the password, marks the token used, 204.
  An ordinary/filtered access token is NEVER sufficient to set a password.
  Admin password reset deferred (documented).
- **S5 — Audit**: `password_set` (actor = the user, organization = None, safe
  metadata `{"method": "setup_token"}`) and `invitation_issued` (actor =
  admin, org context, metadata `{"expires_at": ...}`) events. Never log
  passwords, raw tokens, or hashes.
- **S6 — Throttling**: anonymous throttle on login and set-password
  (30/min per IP, documented); configured via DRF built-in throttling.
- **S7 — Tests**: correct/incorrect login; inactive account (same 401);
  logout + revoked-token reuse; throttle (429); session + CSRF preserved;
  invitation flow (valid, single-use, expired, invalid, access-token
  rejection, weak password, safe audit); org isolation; full-suite
  regression.
- **S8 — Docs**: README (auth endpoints, token no-expiration, invitation
  flow, throttling), contract changelog row, ODD spec (no mirror).

## Tasks

| ID | Specs | Description | Status |
| --- | --- | --- | --- |
| T1 | S4,S5 | `PasswordSetupToken` model (user FK, SHA-256 hash, TTL, single-use) + `PASSWORD_SET`/`INVITATION_ISSUED` actions + migration `0005` | done |
| T2 | S2,S3,S6 | accounts: `LoginView`, `LogoutView`, `SetPasswordView` + serializers + urls + throttle | done |
| T3 | S4,S5 | organizations: `UserInviteView` + route (FINANCE_ADMIN, token issuance, audit) + throttle settings | done |
| T4 | S7 | `accounts/tests_login.py` (27 tests) | done |
| T5 | S8 | README + contract changelog + ODD log | done |
| T6 | S8 | Validation: check, makemigrations --check, full suite isolated, diff + secret review, report | done |

## Log

- L1: user request verbatim (abbreviated): "Sesión nocturna: cierre de Slice 4
  y diseño de Slice 5 … habilitar login seguro … No modifiques archivos …
  espera mi aprobación." (audit + proposal turn).
- L2 (user-approved decisions): (1) keep DRF Token + Session, no SimpleJWT,
  no new deps. (2) `POST /api/v1/auth/login/` and `POST /api/v1/auth/logout/`
  with safe responses, current-token revocation, throttling. (3) resolve
  initial password setup safely: an ordinary/filtered access token must NOT
  be sufficient to take over an account without a password; propose an
  activation/invitation flow compatible with the system. (4) reject inactive
  accounts, preserve immediate invalidation on deactivation, avoid user
  enumeration, never log passwords or tokens. (5) document that DRF tokens
  do not expire automatically; do not simulate expiration; logout revokes the
  current token. (6) tests for correct/incorrect login, inactive account,
  logout, revoked-token reuse, throttling, sessions and CSRF, isolation,
  regressions. (7) do not weaken existing org permissions or unnecessarily
  modify previous slices.
- L3 (implementation): 27 login tests green; full suite 176 OK, exit 0;
  `check` and `makemigrations --check` clean; migration `0005` applied;
  README + contract changelog updated; no mirror created (per user
  instruction). Test fixes during implementation: superuser invite fixture
  needed a membership (404 vs 403), DRF Token is OneToOne per user (logout
  test rewritten for another user's token), and the audit-metadata assertion
  checked the substring "token" inside the method name "setup_token".
