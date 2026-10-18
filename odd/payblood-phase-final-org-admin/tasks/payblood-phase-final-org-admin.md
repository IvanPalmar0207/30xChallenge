# PayBlood — Slice final: administración global de organizaciones

## Header
Implementar la administración global de organizaciones para el superadministrador
(solo global), con creación atómica de organización + admin inicial, auditoría
reutilizada, aislamiento preservado y una sección Angular nueva. Sin staging,
commits, push ni migraciones aplicadas a la DB de desarrollo.

## Specs
- S1. Preflight: inspeccionar rama/estado/últimos commits/diff completo; revisar
  AUTH_USER_MODEL, Organization, OrganizationMembership, roles, permisos, auth,
  auditoría, rutas, serializers, frontend, tests; reutilizar convenciones;
  identificar equivalents en Django Admin/API; presentar plan + lista de
  archivos; no borrar/reinicializar/revertir nada; no staging/commits/push
  automáticos; no mostrar secretos.
- S2. Funcionalidad global (solo superadministrador): (1) consultar
  organizaciones; (2) crear organización; (3) consultar estado; (4) modificar
  campos administrativos permitidos por el modelo; (5) activar/desactivar solo
  si el modelo lo permite (status active/inactive existe); (6) asignar usuario
  inicial FINANCE_ADMIN; (7) consultar usuarios disponibles sin exponer info
  sensible. Adaptar al modelo real, sin inventar campos ni duplicar endpoints.
- S3. Autorización global y aislamiento: solo superuser global; FINANCE_ADMIN
  de una org NO concede admin de otras; is_staff NO concede por sí solo;
  verificación en servidor en cada endpoint; cliente nunca asigna
  is_superuser/is_staff/permisos globales/roles arbitrarios; no modificar la
  org propietaria mediante campos del cliente; aislamiento entre orgs en toda
  consulta; org inactiva niega acceso a sus recursos; respuestas coherentes con
  el patrón de autorización (404 uniforme donde aplique).
- S4. Creación org + admin inicial atómicas: si falla membresía o auditoría →
  rollback total; admin inicial FINANCE_ADMIN solo dentro de esa org; sin
  privilegios globales Django; usuario existente se reutiliza sin tocar
  password/privilegios; usuario inexistente → flujo seguro explícito respetando
  el ciclo de vida actual (create_user sin password + invitación setup token);
  no inventar emails/usernames/passwords; buscar cuenta superadmin en dev sin
  imprimir secretos (verificado en preflight: NO existe); detenerse pidiendo el
  dato concreto si se necesita info personal; nunca passwords por defecto ni
  elevación de privilegios desde la UI.
- S5. Auditoría: reutilizar AuditEvent/_audit; registrar organización creada,
  datos modificados, activada/desactivada, admin inicial asignado; actor,
  organización afectada, acción, target, fecha, metadata segura; jamás
  passwords/tokens/hashes/headers; operación y auditoría en misma transacción.
- S6. UI: sección de administración global con diseño PayBlood; visible solo a
  autorizados sin tratar la visibilidad como seguridad; listado, formulario de
  creación, selección de admin inicial, estados loading/success/error;
  validaciones y confirmación en acciones disruptivas; sin passwords/secretos;
  mantener facturas/vendors/policies/membresías/auth/dashboard intactos; sin
  features ajenas.
- S7. Pruebas mínimas: (1) anónimo sin acceso global; (2) usuario normal sin
  acceso; (3) FINANCE_ADMIN no admin otras orgs; (4) superadmin autorizado sí;
  (5) cliente no se asigna privilegios globales ni roles arbitrarios; (6) org +
  membresía atómicas; (7) fallo de auditoría revierte; (8) aislamiento entre
  orgs; (9) usuarios/membresías inactivos sin acceso indebido; (10) entradas
  inválidas → respuestas controladas, nunca 500; (11) cuenta superadmin
  existente no pierde datos/privilegios; (12) rutas anteriores siguen OK.
  Solicitudes API reales, sin mocks que eviten la lógica de autorización.
- S8. Validación despliegue: backend/frontend en entornos aislados; `manage.py
  check`; `makemigrations --check`; NO aplicar migraciones a dev/prod durante
  la tarea; migraciones solo si el modelo cambia de verdad (AlterField choices
  de auditoría); build de producción frontend; revisar diff ajeno al alcance y
  secretos; no afirmar Postgres verificado sin probarlo; no desplegar nada.
- S9. Informe final: resumen; rutas API y permisos exactos; ubicación en
  Angular; archivos modificados y migraciones; pruebas con comandos/exit
  codes/conteos reales; confirmación de que la cuenta existente y credenciales
  no fueron sobrescritas; riesgos/limitaciones; estado final de Git sin
  staging/commits; lista de comprobaciones pendientes antes de producción;
  párrafo final en español. Detenerse al terminar, esperando revisión antes de
  commits o despliegue.

## Tasks
| ID | Spec | Route | Commit |
| --- | --- | --- | --- |
| T1 | S1 | preflight + plan + doc | — (worktree only) |
| T2 | S3 | backend: IsGlobalSuperAdmin + acciones auditoría + migración | — |
| T3 | S2,S4,S5 | backend: serializers + views + urls globales | — |
| T4 | S7,S8 | backend: tests_admin_organizations + regresión + checks | — |
| T5 | S6 | frontend: models/capabilities/shell/routes + organizations-admin | — |
| T6 | S7,S8 | frontend: spec + suite + build | — |
| T7 | S8 | checks Django + migraciones + git diff --check | — |
| T8 | S9 | informe final + párrafo ES | — |

## Log
- L1: brief del usuario — implementar administración global de organizaciones
  (solo superadmin) antes del despliegue: preflight obligatorio; alcance funcional
  (listar/crear/estado/editar/activar-desactivar/asignar admin inicial/consultar
  usuarios); autorización global y aislamiento (FINANCE_ADMIN no vale fuera de su
  org; is_staff no concede; verificar en servidor; cliente nunca asigna
  privilegios globales); creación atómica org+admin (reutilizar usuario o flujo
  seguro; no inventar datos personales; buscar superadmin sin imprimir secretos;
  detenerse si falta un dato personal y pedirlo); auditoría reutilizada
  transaccional; UI en Angular con diseño actual, estados y confirmaciones;
  pruebas exigidas (12 casos incl. regresión y no-500); validación despliegue
  (checks, sin aplicar migraciones a dev/prod, build, diff revisado, sin afirmar
  Postgres); informe final con 9 puntos + párrafo ES; detenerse al terminar.

### Preflight — hallazgos (L2)
- Rama `main`, 7 commits, 33 archivos M + 43 ?? en worktree (trabajo previo sin
  commitear). No hay staging/commits/push automáticos.
- No existe funcionalidad global en la API: OrganizationViewSet lista solo las
  orgs del usuario con membresía activa; superuser sin membresía → 404
  (test existente `test_superuser_without_membership_gets_no_access`).
  Django Admin permite crear orgs pero sin auditoría ni atomicidad: la sección
  nueva lo complementa con flujo auditable (no duplica endpoints de la API).
- Modelo: Organization (name, status active/inactive, timestamps);
  OrganizationMembership (user, org, role, is_active, unique user+org);
  AuditEvent append-only con _audit() transaccional; PasswordSetupToken
  (invitación one-time, hash SHA-256, raw mostrado una vez).
- Permisos org-scoped: IsActiveOrganizationMember(-InUrl) / FinanceAdmin /
  Approver / InvoiceCreator; patrón 404 uniforme (HidingByNotExisting);
  GRANTABLE_ROLES excluye FINANCE_ADMIN para miembros (se respeta: solo el
  superadmin global podrá asignar FINANCE_ADMIN en la creación).
- AUTH_USER_MODEL: no definido → User por defecto de Django
  (django.contrib.auth). Frontend usa UserProfile con memberships.
- Contrato identidad: /auth/me/ y login NO exponen flags de staff/superuser.
  Para la visibilidad de la sección se añade `is_global_admin` (derivado,
  solo sesión propia; el servidor sigue siendo la autoridad) — decisión
  declarada en el plan.
- DB dev: NO existe ningún superuser ni staff (verificado sin imprimir
  secretos). No se inventan credenciales; si se requiere una cuenta global
  para pruebas manuales se pedirá el email concreto al usuario.
### Resultado (L3)
- Backend: `IsGlobalSuperAdmin` (solo is_superuser; is_staff NO vale; no-autenticados → 401,
  autenticados no-superuser → 404 uniforme). Vistas globales: list/create org (POST) con
  creación atómica org + membresía FINANCE_ADMIN + auditorías (ORGANIZATION_CREATED,
  ACCOUNT_CREATED, MEMBERSHIP_CREATED, INVITATION_ISSUED) y setup token one-time para cuenta
  nueva; detail (GET/PATCH name+status) con ORGANIZATION_UPDATED / ACTIVATED / DEACTIVATED;
  admin/users/?q= candidatos id/username/email (sin datos sensibles). Serializers:
  GlobalOrganizationCreateSerializer (name+admin_email; cliente nunca fija roles ni flags),
  GlobalOrganizationUpdateSerializer (name/status), GlobalUserCandidateSerializer.
- Migración 0008_org_admin_audit_actions: solo AlterField de choices en auditevent.action.
  GENERADA sin aplicar (dev/prod intactas).
- Contrato aditivo: `/auth/me/` y login exponen `is_global_admin` (derivado de la sesión,
  solo visibilidad UI; el servidor re-valida is_superuser en cada endpoint).
- Frontend: `/app/admin/organizations` con OrganizationsAdminPage (listado, creación con
  selector de candidatos, activar/desactivar con confirmación, estados
  loading/ready/forbidden/error, token one-time mostrado una vez); nav 'Global admin'
  gated por capability `adminGlobalOrganizations` (derivada de is_global_admin).
- Pruebas backend: 17 tests nuevos en tests_admin_organizations (anónimo/normal/FINANCE_ADMIN
  denegados; superadmin autorizado; sin privilegios globales del cliente; atomicidad;
  rollback ante fallo de auditoría; aislamiento; inactivos; entradas inválidas; superuser
  reutilizado sin perder privilegios; regresión) + regresión completa 322 TESTS OK.
  Frontend: 98 TESTS OK (suite completa), build exit 0, git diff --check exit 0.
- Git: worktree 82 entradas, sin staging/commits/push (HEAD 7c48773). Cuentas dev intactas
  (verificado en shell, sin secretos). DB dev sin migrar ni mutar.

### Superuser global creado (L4)
- Cuenta global creada a petición del usuario: username=email
  palmar.ivan0205@gmail.com, is_active=True, is_staff=True, is_superuser=True,
  password usable (la contraseña la proporcionó el propietario; nunca se
  imprime ni se almacena en el repo). 0 membresías.
- Verificado end-to-end contra el backend dev (127.0.0.1:8000):
  POST /auth/login/ -> JWT OK; /auth/me/ -> email, is_global_admin=True,
  memberships=[]; GET /admin/organizations/ -> Dev Org (active), Other Org
  (active). La sección 'Global admin' del frontend quedará visible con esta
  sesión.
- Recordar (invariente del contrato): el superuser sin membresías NO ve facturas/
  vendors/policies ni la lista org-scoped (análogo al test existente
  test_superuser_without_membership_gets_no_access). Para esas vistas hay que
  crear membresías org-scoped por los endpoints estándar.
- La migración 0008 (choices de auditoría) sigue SIN aplicar, como exige el
  brief: no se migra dev/prod durante la tarea.
