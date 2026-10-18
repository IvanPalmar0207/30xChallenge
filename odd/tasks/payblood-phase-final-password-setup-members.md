# PayBlood — Setup de contraseña y administración de miembros

## Header
Completar el onboarding y la administración de usuarios: (A) flujo de contraseña
inicial por setup_token y (B) administración de miembros por FINANCE_ADMIN.
El backend de ambas funciones ya existe y está probado; la tarea cierra las
brechas de frontend y de cobertura de tests. Sin staging/commits/push, sin
migraciones a dev/prod, sin cambiar AUTH_USER_MODEL.

## Specs
- S1. Preflight: revisar git, flujo auth/setup_token/roles/permisos/auditoría/
  rutas/serializers/frontend/tests; reutilizar; presentar plan; no staging en
  commits; no mostrar secretos/tokens/passwords.
- S2. A-backend: reutilizar SetPasswordView seguro existente; añadir rechazo de
  token de cuenta inactiva; token validado (hash, TTL 72h, single-use atómico);
  sin sesión ni tokens de acceso devueltos; sin cambio de roles/privilegios;
  throttle 30/min existente; validadores Django existentes.
- S3. A-frontend: página pública /setup-account?token=... con password +
  confirmación, validación, estados loading/success/error, limpieza del token
  de la URL, enlace a login, sin persistir credenciales, en inglés.
- S4. B-backend: reutilizar MembershipListCreateView, MembershipDetailView,
  UserCreateView, UserActivationView, UserInviteView; GRANTABLE_ROLES
  (OPERATOR/APPROVER/AUDITOR); FINANCE_ADMIN no delegable; sin autopromoción;
  superuser intocable; whitelist de campos; transacciones con auditoría.
- S5. B-frontend: página /app/organizations/:id/members (FINANCE_ADMIN): listar
  miembros, crear cuenta, invitar (setup token mostrado una vez), cambiar rol,
  activar/desactivar; estados explícitos; confirmación para acciones
  disruptivas; crumb nuevo.
- S6. Pruebas: A (10 casos: válido, autenticable post-setup, inválido, expirado,
  reutilizado, sin secretos en respuesta/auditoría, sin cambiar privilegios,
  cuenta inactiva, contraseña inválida/confirmación distinta, sin sesión nueva)
  y B (11 casos: anónimo, roles no-admin, FINANCE_ADMIN roles permitidos,
  sin delegar FINANCE_ADMIN, sin privilegios globales, sin cross-org, org o
  membership inactiva, sin 500 en duplicados, rollback transaccional, rol con
  efecto en la siguiente request, cuentas existentes intactas) + regresión.
- S7. Validación: suites backend/frontend completas, manage.py check,
  makemigrations --check, build Angular, git diff --check; sin aplicar
  migraciones a dev/prod; sin deploy.
- S8. Informe: resumen A y B, rutas/endpoints, seguridad del token, operaciones
  y roles, matriz de autorización, archivos/migraciones, pruebas con
  comandos-conteos, riesgos, estado Git, pasos pre-producción; párrafo ES;
  detenerse sin commits/push.

## Tasks
| ID | Spec | Route | Commit |
| --- | --- | --- | --- |
| T1 | S1 | preflight + plan + doc ODD | — (worktree only) |
| T2 | S2,S4 | backend: filtro cuenta inactiva + validaciones | — |
| T3 | S3 | frontend: página setup-account + ruta + spec | — |
| T4 | S5 | frontend: organizations-members (page/service/models) | — |
| T5 | S6 | backend: tests A (roles/privilegios/inactiva) y B (rol/membership/org inactiva) | — |
| T6 | S6,S7 | frontend: spec members + suite + build | — |
| T7 | S7 | checks + git diff --check | — |
| T8 | S8 | informe final + párrafo ES | — |

## Log
- L1: brief del usuario — implementar setup de contraseña (endpoint público
  limitado, validar token/vigencia/un-solo-uso, set_password seguro, invalidación
  atómica, sin tokens en respuestas, sin cambiar roles/privilegios, sin
  enumeración, throttle, página Angular /setup-account) y administración de
  miembros FINANCE_ADMIN (consultar, crear cuenta, asignar roles permitidos,
  añadir usuario existente, cambiar rol, activar/desactivar, estado de
  invitación sin exponer token; separación de privilegios sin delegar
  FINANCE_ADMIN, sin autopromoción, superuser intocable, whitelist, atómico),
  auditoría reutilizada, pruebas obligatorias (22), validación (checks, sin
  migrar dev/prod), informe final; detenerse sin commits/push.

### Preflight — hallazgos (L2)
- AUTH_USER_MODEL sin definir (User por defecto de Django), no se cambia.
- A-backend COMPLETO: SetPasswordView (post /auth/set-password/) con
  PermissionClasses=[AllowAny], throttle LoginRateThrottle 30/min,
  PasswordSetupToken (hash sha-256, expires_at 72h, used_at single-use,
  select_related user), set_password + save, invalidación used_at atómica,
  _audit PASSWORD_SET metadata={"method":"setup_token"}, 204 sin tokens.
  Tests previos: test_set_password_with_valid_token / token_single_use /
  expired_token / invalid_token / does_not_accept_access_token /
  weak_password_rejected / audit_event_safe_metadata / audit_failure_rolls_back.
- A-brechas: no filtra user__is_active=True en la consulta del token (cuenta
  inactiva podría completar setup sin poder loguearse después — se bloquea
  explícitamente); sin test de que el setup no altera roles/privilegios.
- B-backend COMPLETO: MembershipListCreateView (GET/POST), MembershipDetailView
  (PATCH rol/is_active, self y superuser protegidos), UserCreateView (atómico,
  password unusable, whitelist), UserActivationView, UserInviteView (token
  una vez), sus serializers con whitelist y GRANTABLE_ROLES.
- B-brechas de cobertura: sin test de PATCH rol (efecto, negación FINANCE_ADMIN,
  self), sin test de crear membership para usuario existente con rol
  permitido/rechazado, sin test org inactiva en administración.
- Frontend: NO existe página de setup ni página de administración de miembros;
  organizations.html solo lista las orgs del usuario con su rol.
- Rutas actuales: /api/v1/auth/set-password/; /api/v1/organizations/{pk}/
  memberships/ y memberships/{pk}/, users/, users/{id}/invite/.
- Git: main, HEAD 7c48773, 33 M + 48 ??; sin staging/commits. DB dev sin migrar.
### Resultado (L3)
- A-backend: SetPasswordView reutilizado sin duplicación; añadido filtro
  user__is_active=True (una cuenta desactivada no puede completar el setup;
  el token queda sin quemar). Setup envuelve set_password + invalidación
  used_at + auditoría en una transacción. Throttle 30/min existente.
  Nuevos tests: token de cuenta inactiva rechazado; el setup no cambia
  roles/privilegios. apps.accounts: 53 tests OK (incluye 10 previos + 2).
- A-frontend: nueva página pública /setup-account?token=... -> 2 inputs
  (password + confirmación), validación local, limpieza del token de la URL
  (replaceUrl), sin persistencia, estado success con enlace a /login,
  error genérico (nunca filtra token expirado/válido). AuthService
  +setPassword(setup_token, password). setup.spec.ts 4 PASS; login 6 PASS.
- B-backend: sin cambios de código (ya implementado): MembershipListCreateView,
  MembershipDetailView, UserCreateView, UserActivationView, UserInviteView con
  GRANTABLE_ROLES (OPERATOR/APPROVER/AUDITOR), sin delegación de FINANCE_ADMIN,
  sin autopromoción, superuser intocable, whitelist, transacciones con auditoría.
  tests_membership.py pasa de 26 a 27 (nuevo test_existing_account_keeps_
  password_and_privileges -> caso 21 del brief).
- B-frontend: nueva página /app/organizations/:id/members con OrganizationsMembers
  Service/models (contratos reales), listado, creación de cuenta + rol,
  invitación one-time (token mostrado una vez con Hide), añadir cuenta existente
  por id, cambio de rol, activar/desactivar con confirmación; enlace
  'Members' en organizations.html para FINANCE_ADMIN; RouterLink añadido;
  crumb 'Members' (MEMBERS_CRUMB_RE). organizations-members.spec.ts 5 PASS.
- Regresión backend completa: 325 tests OK (322 previos + 2 accounts + 1
  membership). Suite frontend completa: 16 archivos / 110 tests OK (101 + 4
  setup + 5 members; login pasó de 6). Build producción exit 0; manage.py check
  0 issues; makemigrations --check: No changes detected (sin migraciones
  nuevas); git diff --check exit 0.
- Git: main, HEAD 7c48773, 33 M + 50 ?? (worktree), sin staging/commits/push;
  DB dev sin migrar ni mutar (salvo la cuenta superuser pedida previamente).
- Limitaciones: sin envío de correo en el proyecto (el setup link se entrega
  out-of-band, el admin lo copia una vez); 'añadir cuenta existente' requiere
  el id numérico del usuario (no hay búsqueda de correo para evitar
  enumeración de cuentas); la confirmación de contraseña se valida en el
  frontend (el backend solo recibe setup_token+password, contrato existente).

### Diagnóstico: opción Members no visible (tarea de corrección)
- Causa raíz: el enlace Members está dentro de la tabla de organizaciones y se
  muestra por fila SOLO si roleOf(org.id) === 'FINANCE_ADMIN'. La tabla lista
  solo ls orgs con membresía activa del usuario (GET /organizations/ favorecido
  por backend). Las cuentas superuser globales (palmar.ivan0205@gmail.com,
  ipalmar1) tienen 0 membresías → /organizations/ = [] → sin filas → sin enlace.
  Eso NO es un bug: es el aislamiento por contrato (el test existente
  test_superuser_without_membership_gets_no_access lo fija).
- Verificado contra API real: dev@payblood.test y martinezpalmar.ivan0205@gmail.com
  (FINANCE_ADMIN con membresía activa) listan su org y /memberships/ responde
  200; OPERATOR/other devuelven 404 en memberships de otra org.
- Código correcto: la condición, la ruta /app/organizations/:id/members y el
  routerLink con org.id real pasan specs (7/7 en organizations.spec con 2 tests
  nuevos: FINANCE_ADMIN ve el enlace, OPERATOR/APPROVER no).
- Cambios: solo tests (organizations.spec.ts +provideRouter y 2 tests de
  visibilidad del enlace); sin cambios de lógica de autorización. Suite 112 OK,
  build OK, git diff --check OK.
