# PayBlood — Mejora UX/UI: alta de usuarios y configuración de contraseña

## Header
Mejorar la experiencia del alta de usuarios (Members) y la página de configuración
de contraseña inicial (setup-account): textos guiados, panel de enlace con copiar/
mostrar/ocultar/regenerar, estados de carga/éxito/error y accesibilidad. Solo
frontend; el backend ya lo permite todo (regeneración segura incluida). Sin
staging, commits, push, DB ni migraciones.

## Specs
- S1. Preflight de repo, módulo members, setup, endpoints invite/set-password,
  TTL 72h real, un solo uso, mensajes reales del backend; presentar plan antes
  de editar; conservar cambios; sin staging/commits.
- S2. Members: formulario «Create user» (email + rol delegable), texto
  informativo, botón «Create user» / «Creating user…» deshabilitado durante el
  envío; respuestas por tipo de error real (duplicado, inválido, sin permiso,
  inesperado) sin filtrar detalles.
- S3. Panel post-creación: encabezado «User created successfully», sección
  «Password setup link», enlace real `{origin}/setup-account?token=…` truncado
  visualmente (valor completo al copiar), controles Copy/Show/Hide/Close/
  Generate new link (solo con confirmación; el backend invalida el anterior en
  la misma transacción, TTL 72h y un solo uso por contrato real).
- S4. Estado «usuario creado pero falló la generación del enlace»: mensaje
  honesto, sin enlace ficticio, solo acción que exista en backend.
- S5. Setup-account: textos del brief («Set your password», errores por token
  inválido/expirado/usado, inactivo, conexión, inesperado), toggle de visibilidad
  de contraseña, sin envíos duplicados, success con «Go to sign in» → /login.
- S6. Seguridad: sin tokens en localStorage/sessionStorage/logs/errores, sin
  analítica, la UI no sustituye la autorización, si el backend no puede
  configurarse no se inventa (email: no se envía, documentado como limitación).
- S7. Pruebas frontend: 12 casos (instrucciones post-creación, estados de carga/
  error, copy con valor completo, fallo de clipboard, mostrar/ocultar, sin
  enlace inventado, confirmación de regeneración, validación de password,
  navigate a /login real, errores de token/conexión, sin duplicados, diseño
  responsive). Suite completa + build + git diff --check.
- S8. Informe: archivos, cambios UX, estados/mensajes, comportamiento del enlace,
  garantías, pruebas reales, limitaciones (sin mail), estado Git, párrafo ES.

## Tasks
| ID | Spec | Route | Commit |
| --- | --- | --- | --- |
| T1 | S1 | preflight + plan + doc ODD | — (worktree only) |
| T2 | S2,S4,S6 | members: componente (estados + lógica enlace/copy/regeneración) | — |
| T3 | S2,S3,S6 | members: template y estilos (form, panel, tabla mejorada) | — |
| T4 | S5,S6 | setup-account: template, textos y validaciones | — |
| T5 | S7 | specs members + setup + suite completa + build | — |
| T6 | S7,S8 | git diff --check + informe + párrafo ES | — |

## Log
- L1: brief usuario: mejorar UX/UI alta de usuarios y setup inicial (creación
  guiada, confirmación de cuenta, generación/copia/ocultación del enlace,
  explicación de cómo compartirlo con seguridad, regeneración SÓLO si el backend
  lo permite, página de setup mejorada, mensajes de validación/éxito/error/
  expiración/uso previo, instrucciones a login, estados de carga y sin envíos
  duplicados). No: registro público, recuperación de contraseña, envío de mail,
  MFA, roles, auth, aislamiento, finanzas, dependencias. Si UX exige backend
  inexistente → documentar y pedir autorización. Pruebas de frontend y
  validación; sin staging/commits/push; informe final y detenerse.
- L1b: extra del usuario: «hazlo también para members al momento de darle issue
  setup link para que la persona que crea la cuenta sepa qué enlace compartir y
  revisa la UI de members, me gustó pero la lista desplegable y los botones
  pueden mejorar».
- L2: preflight. Backend INABROTABLE: UserCreateView (atomico, email duplicado
  -> 400 "A user with this email already exists."), UserInviteView (invalida
  previos no usados, TTL SETUP_TOKEN_TTL_HOURS=72, un solo uso, respuesta
  {setup_token, expires_at}; 403 superuser), set-password (400 "Invalid or
  expired setup token.", 204 ok, sin tokens en respuesta). Regeneración SEGURA
  y AUTORIZADA por el endpoint de invite -> se implementa con confirmación.
  Frontend: members (form, banner verde con token crudo, hide, select inline,
  addExisting por id) y setup (valida, limpia token de URL, sin persistencia,
  204->success, mensajes genéricos EN). Iconos pb-icon (check/x/alert/search/
  arrowRight/close/loader/chevronDown). Idioma: inglés.

### Resultado (L3)
- Members complejo: form «Create user» con hint de password inicial, botón
  deshabilitado durante el envío (sin duplicados); respuestas por tipo de error
  real (campo email duplicado -> 'This email is already registered...',
  403/404 -> permisos, 400 -> revisar input, resto -> inesperado). Panel
  post-creación 'User created successfully' con 'Password setup link'
  (origen real + /setup-account?token=...), campo visible truncado con token
  enmascarado por defecto, controles Show/Hide/Copy/Close/Generate new link
  (confirmación requerida; regenera por el endpoint auditado que invalida el
  anterior), avisos 'Link copied' / fallo de portapapeles sin bloquear. Estado
  'User created, but access is not ready' si falla la generación (sin enlace
  inventado). Botón 'Issue setup link' por fila reutiliza el mismo panel.
- Setup-account: 'Set your password' con email/confirmación, toggles de
  visibilidad accesibles (aria-pressed), aviso inline de coincidencia,
  botón deshabilitado durante el envío, errores por token inválido/expirado/
  usado (uniforme, sin enumeración), conexión (status 0), inesperado;
  éxito 'Password set successfully' -> 'Go to sign in' -> /login real.
  Nota: el backend responde el MISMO 400 para token inválido, expirado, usado
  o cuenta inactiva -> la UI los trata uniforme (anti-enumeración), y el
  mensaje 'inactive account' del brief no se distingue por contrato.
- Reactivos: tabla members con select de rol estilizado y botones accionables
  (actions-cell flex, mejor responsive).
- Seguridad conservada: token solo en memoria (nunca localStorage/URL/request
  de log; se limpia del query string al abrir setup; close() descarta el panel
  y su estado); la UI no reemplaza la autorización del backend; regeneración
  solo con confirmación y por endpoint auditado; nada de mail simulado.
- Pruebas: specs members 10 + setup 8 + orgs 7 = 24 PASS; suite completa
  16 archivos / 120 tests PASS; npx ng build exit 0; git diff --check exit 0.
- Git: main, HEAD 7c48773, 33 M + 53 ??, sin staging/commits/push; sin DB ni
  migraciones; sin dependencias nuevas.
- Limitaciones: sin envío de correo (el enlace se entrega out-of-band por el
  admin; documentado); sin distinción 'cuenta inactiva' por contrato uniforme;
  sin Playwright/Puppeteer -> visual NOT VERIFIED (validado por tests jsdom).

### Sección 12 — Mejora issue setup link + diseño Members (L4)
- Hallazgo B: el backend NO expone has_usable_password/setup_pending en
  MembershipSerializer; no se añade etiqueta engañosa de estado de acceso.
  Propuesta mínima (requiere autorización): añadir campo calculado
  has_password al MembershipSerializer (sin cambiar auth ni tokens). No se
  cambia el contrato en esta tarea.
- Implementación: confirmación previa a 'Issue setup link' (textos async),
  panel contextual con correo del miembro visible, copia/muestra/oculta/cierra
  con descarte del token, estado vacío útil ('No members in this organization
  yet' + 'Create first user'), error de carga con retry, filtro de la fila del
  actor (auth current user) para evitar confusiones y auto-acciones, select de
  rol estilizado (chevron propio, foco, sin FINANCE_ADMIN), jerarquía de
  botones (primary/ghost/destructive con confirmación), responsive.

### Sección 12 — resultado (L5)
- Issue setup link: al pulsar se abre un diálogo de confirmación inline
  (Cancel / Generate link) que identifica el correo del miembro y explica que
  el enlace anterior dejará de funcionar (el backend invalida los no usados en
  la misma transacción). Durante la llamada el botón se deshabilita
  (invitingFor) -> sin duplicados. Panel contextual 'Setup link generated'
  con 'For: <email>', copiar (valor completo), mostrar/ocultar máscara, cerrar
  (descarta token de la memoria) y 'Generate new link' con confirmación.
- Filtro del actor: visibleMemberships() excluye la fila del usuario autenticado
  (evita confusión y auto-acciones; la tabla no muestra el propio rol).
- Estados por miembro: SOLO se muestra membership.is_active (dato real). El
  backend NO expone has_usable_password/setup_pending -> NO se añade etiqueta
  'pendiente/configurado' engañosa; se documenta la propuesta mínima
  (campo has_password en MembershipSerializer) que requeriría autorización.
- Tabla/selects/botones: actions-cell en flex (sin nowrap forzado), select con
  chevron propio, altura/foco/disabled, botones ghost/primary/destructive
  (is-danger en Deactivate con confirmación), jerarquía, responsive 860px.
- Estados vacío ('No members in this organization yet' + 'Create first user'
  con focusCreate) y error ('We could not load members' + Retry) distinguidos.
- Pruebas: organizations-members.spec.ts 15/15 (13 casos del brief + cancelación
  de confirmación + filtro del actor + estado vacío/error). Suite completa
  16 archivos / 125 tests PASS; npx ng build exit 0; git diff --check exit 0.
- Git: main, HEAD 7c48773, 33 M + 53 ??, sin staging/commits/push; sin DB,
  migraciones ni dependencias nuevas; sin cambios de autorización.
- Limitaciones: sin has_usable_password en backend (no se distingue 'ya
  configurada' vs 'pendiente'; el mensaje 'ya tiene acceso configurado' del
  brief se cubre con copy genérico por contrato); sin envío de correo; visual
  responsive validado por CSS/tests jsdom (sin navegador headless).
