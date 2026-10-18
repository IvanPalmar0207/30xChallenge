# PayBlood — Flujo `received` + PDFs de prueba + auditoría UX/UI (Etapas 1–3)

## Header

Trabajo sobre el repo PayBlood existente, en 3 etapas ordenadas: (1) completar y
validar el flujo de facturas `received`, (2) generar PDFs sintéticos de prueba
con matriz ligada al brief, (3) auditoría UX/UI y correcciones. Reglas: no
commits/staging/push, no mutación de la base de desarrollo, sin secretos, no
inventar endpoints/estados/permisos, conservar trabajos previos.

## Specs

- **S1 — Causa raíz de `received`**: diagnosticar la ruta/componente de detalle de
  factura, servicios/modelos frontend, endpoints reales de facturas/evaluación,
  máquina de estados y motor de políticas, permisos/membresías, y pruebas de
  facturas, evaluación y aprobación. Identificar por qué `received` no permite
  acciones.
- **S2 — Implementación `received`**: solo acciones avaladas por contrato y
  permisos; "Evaluar factura" para OPERATOR/FINANCE_ADMIN cuando el backend lo
  soporta; endpoint existente; la respuesta real actualiza la UI; loading,
  bloqueo anti-duplicado, errores recuperables, mensajes de resultado;
  aislamiento por org; AUDITOR nunca modifica; APPROVER solo cuando estado y
  permisos lo autoricen; evaluación ≠ aprobación humana; sin botones para
  transiciones inexistentes; estados blocked/escalated/pending_approval/
  approved/rejected con acciones y explicaciones correctas, sin transiciones
  inválidas. Si la API no soporta algo: documentar el conflicto y la
  modificación mínima; nunca un bypass de permisos.
- **S3 — Aceptación E1** (pruebas con flujo real): (1) `received` muestra la
  acción solo a roles autorizados; (2) evaluación exitosa actualiza estado y
  muestra el resultado real; (3) errores sin simular éxito; (4) clics repetidos
  sin solicitudes concurrentes; (5) sin permisos no se opera por UI ni API;
  (6) aislamiento entre orgs; (7) aprobación respeta estado y rol; (8) estados
  terminales sin acciones inválidas; (9) pruebas previas de facturas, políticas,
  extracción y permisos siguen pasando. Frontend backend y build.
- **S4 — PDFs sintéticos**: casos correctos y límite según brief real y
  extractor real (texto seleccionable, multipágina, tablas y totales, fechas y
  decimales variados, monedas del contrato, opcionales ausentes, obligatorios
  ausentes, datos contradictorios, IDs variados, escaneado si el extractor lo
  admite, baja calidad si representable seguro, PDF vacío/corrupto, advertencias
  deterministas, un caso válido y uno inválido por regla testeable). Sin inventar
  monedas/reglas/umbrales: obtenerlos de brief, modelos, serializers y políticas.
  Datos ficticios, IDs de caso únicos, expected por caso, sin secretos ni
  contenido malicioso; en carpeta de fixtures según convención; sin sobrescribir
  fixtures existentes.
- **S5 — Matriz y ejecución E2**: matriz PDF → (archivo, escenario, campos
  esperados, resultado esperado, validaciones/advertencias, comportamiento de
  error, regla del brief). Separar extracción de ciclo de vida (extracción nunca
  crea/aprueba/paga). Suite automatizada sin llamadas reales a IA; integración
  real como paso separado con coste registrado si disponible; verificar que los
  PDFs abren y el texto es legible; ejecutar extracción + facturas + regresión.
  Un PDF sin prueba que lo use no declara cobertura.
- **S6 — Auditoría UX/UI**: pantallas reales (login, dashboard, facturas lista y
  detalle, evaluación/aprobación, vendors, policies, extracción), estados de
  carga/error/vacío/formularios/permisos; jerarquía, consistencia, usabilidad,
  responsive, accesibilidad, formularios, tablas, feedback, estados de negocio
  reales, permisos ocultando acciones, contenido sin placeholders ("Live data is
  next"), datos financieros solo del backend. Correcciones pequeñas y
  coherentes, sin nuevas deps, sin cambiar reglas/permisos/endpoints para
  resolver visuales, sin datos ficticios. Estructural/seguridad/business-rule:
  documentar y esperar autorización. Tabla final pantalla/problema/severidad/
  corrección/evidencia/estado.

## Tasks

| ID | Spec | Ruta | Descripción | Estado |
| --- | --- | --- | --- | --- |
| T1 | S1 | E1 | Diagnóstico causa raíz `received` (backend + frontend) | done |
| T2 | S2 | E1 | Implementar acción Evaluar factura + estados/acciones por rol | done |
| T3 | S3 | E1 | Pruebas de aceptación (specs, suite completa, backend, build) | done |
| T4 | S1–S3 | E1 | Documentar resultado E1 (este doc) | done |
| T5 | S4 | E2 | Generar PDFs sintéticos + matriz de pruebas | pending |
| T6 | S5 | E2 | Ejecutar extracción/regresión con los fixtures | pending |
| T7 | S6 | E3 | Auditoría UX/UI + correcciones | pending |

## Log

- **L1 (17-oct, pedido original)**: "PayBlood — Cierre del flujo `received` y
  preparación de PDFs de prueba. Completa estas dos etapas en orden: primero
  corrige y valida el flujo de facturas `received`; después genera un conjunto de
  PDF sintéticos para probar la extracción y los escenarios funcionales descritos
  en el brief original del reto. Reglas obligatorias: ... (ver Specs arriba; sin
  staging, commits ni push; no modificar la base de desarrollo; sin secretos; no
  inventar endpoints/estados/permisos)." + "ETAPA 3 — Auditoría final de UX/UI y
  correcciones ... Finaliza indicando qué mejoras se realizaron, qué problemas
  permanecen y si la aplicación está lista para una revisión manual de
  aceptación."

### E1 — Resultado

- **Causa raíz probada**: el backend ya soporta `POST .../invoices/{id}/evaluate/`
  (permiso `IsActiveOrganizationInvoiceCreator` = OPERATOR/FINANCE_ADMIN; solo
  `status == received`; decisión determinista; transición atómica con auditoría y
  `PolicyDecision`). El frontend nunca implementó la acción: `invoice-detail.ts`
  solo manejaba aprobación humana; `capabilities.service.ts` carecía de
  `canEvaluateInvoice()`; `invoices.service.ts` carecía de `evaluate()` y
  `decision()`. Por eso `received` no mostraba acciones. No es defecto backend.
- **Acciones por estado/rol (UI)**:
  - `received` + OPERATOR/FINANCE_ADMIN → **Evaluate invoice** (POST evaluate/;
    motor decide; resultado real + reason mostrados; refresh del estado real).
  - `pending_approval` + APPROVER → Approve/Reject (POST approval/; existente).
  - Cualquier otro estado (approved/blocked/escalated/rejected) → sin botones;
    nota de estado estática + reason real de la decisión grabada
    (GET .../decision/) + policy version.
  - AUDITOR: solo lectura, nunca acciones.
- **Endpoints usados y permisos comprobados**: `GET .../invoices/{id}/` (cualquier
  miembro activo del org), `POST .../invoices/{id}/evaluate/` (creador de invoices:
  OPERATOR/FINANCE_ADMIN), `GET .../invoices/{id}/decision/` (cualquier miembro
  activo), `POST .../invoices/{id}/approval/` (APPROVER, separación de deberes,
  una decisión). Verificado con JWT de solo lectura contra el backend de dev
  (`/auth/me/` → memberships; `decision/` real de INV-UI-B → `escalated`,
  `due_date_missing`, rules_snapshot, policy_version 1). 2 facturas reales
  `received` (PB-2026-002, INV-1000) confirmadas; **no fueron evaluadas** (no
  mutar la base de desarrollo).
- **Archivos modificados (E1, frontend)**: `invoice-detail.ts` (canEvaluate,
  evaluate(), refresh(), loadDecision(), notas de estado, error persistente),
  `invoice-detail.html` (bloque de evaluación + stateexplain + error global),
  `invoice-detail.scss` (estilos stateexplain/evaluated/actions-error),
  `invoices.service.ts` (+evaluate(), +decision()), `invoices.models.ts`
  (+EvaluationResult), `capabilities.service.ts` (+canEvaluateInvoice()),
  `invoice-detail.spec.ts` (16 tests: roles, evaluación, errores, anti-duplicado,
  409, terminales, aprobación).
- **Pruebas E1 (reales)**:
  - `npx ng test --include="**/invoice-detail.spec.ts"` → 1 archivo / **16 PASS**.
  - `npx ng test` (suite completa) → 11 archivos / **79 PASS** (antes 70).
  - `python manage.py test apps.organizations.tests_invoices apps.organizations.tests_policy
    apps.organizations.tests_approval apps.organizations.tests apps.organizations.tests_vendors
    apps.accounts` → **204 tests OK** (el trace `RuntimeError: boom` es el test
    intencional de fail-safe).
  - `npx ng build` → exit 0 (solo 2 warnings pre-existentes).
  - `git diff --check` → exit 0 (solo warnings CRLF).
- **Limitaciones E1**: no e2e de navegador (sin playwright/puppeteer) → render
  visual real NOT VERIFIED; la evaluación real POST no se ejecutó contra la DB de
  dev (prohibido mutarla) — el POST se validó por tests backend (base aislada) y
  frontend (HTTP mocked); coste/cobros sin verificar (n/d).

### E2 — Resultado

- **Fixtures generados** (`test-artifacts/synthetic-invoices/`, 109 KB, sin
  dependencias nuevas; generador `generate.py` puro Python, pypdf solo verifica):
  C001 digital completo, C002 multipágina, C003 tabla+totales COP, C004 fechas
  dd/mm/aaaa + coma decimal europea, C005 opcionales ausentes, C006 obligatorios
  ausentes, C007 totales contradictorios, C008 tax_id/nº variados, C009 3
  monedas (CAD/JPY/GBP), C010 escaneo rotado JPEG, C011 PDF corrupto, C012 vacío,
  C013 baja calidad JPEG. Datos 100% ficticios, IDs únicos, matriz en README.md.
- **Pruebas que usan los fixtures**: `backend/apps/extraction/tests_synthetic_pdfs.py`
  (20 tests): pipeline de documento (cada PDF con texto seleccionable verificado,
  multipágina, imágenes, vacío→400, corrupto→warning, extensión errónea), gate
  determinista (decimales, fechas, monedas, tax_id, ausentes→absent, cross-field,
  cifras no inventadas) y API end-to-end con mock (`raw_text_extracted=true`,
  `verification_status=not_configured`, **no crea invoice** — lista queda vacía).
- **Regresión extracción**: `python manage.py test apps.extraction` → **55 OK**
  (35 previos + 20 nuevos). Legibilidad: pypdf 0 replacement chars; PIL abre
  ambas imágenes.
- **Limitaciones documentadas (no simuladas)**: coma decimal europea NO se
  normaliza (rama inalcanzable en `_validate_amount`: "1.500,00"→"1.50",
  "1500,00"→"150000.00"; test lo pincha); fechas no ISO rechazadas; sin
  reconciliación subtotal/IVA/total (C007 mantiene el total declarado);
  extracción real con proveedor NO ejecutada en suite (mock); OpenRouter real =
  paso separado, coste NO VERIFICADO; NullVerifier→not_configured (diseño).

### E3 — Resultado (auditoría UX/UI + correcciones)

| Pantalla | Problema | Severidad | Corrección | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- |
| Invoices (lista) | Botón "Upload invoice" con estilos inline, inconsistente con el sistema `pb-btn` | media | Reemplazado por `<a class="pb-btn pb-btn--primary">` | build + spec invoices PASS | PASS |
| Invoices (lista) | Tabla de 7 columnas sin contenedor de scroll → desborde en móvil | alta | Envuelta en `.pb-table-scroll` (overflow-x auto) | build + spec PASS | PASS |
| Invoices (lista) | Filas clicables sin rol/aria para navegación por teclado/lectores | media | `role="link"` + `[attr.aria-label]="'Open invoice …'"` | build + spec PASS | PASS |
| Vendors, Policies, Dashboard (recent), Organizations | Mismas tablas sin scroll horizontal en móvil | media | Mismas envolturas `.pb-table-scroll` | 5/5 specs PASS | PASS |
| Shell (crumb) | Rutas dinámicas (`/app/invoices/:id`) mostraban "App" en el crumb | baja | `crumbFor()` resuelve detalle → "Invoice" | build PASS | PASS |
| Dashboard / Skeleton | cabecera con flex inline (layout menor, se mantiene) | baja | no corregido (decisión: sin rediseños) | — | NOT VERIFIED |
| Landing público | Textos "not implemented yet/planned" | — | intencionales (honestidad), se mantienen | — | PASS |
| Audit | EmptyState "No audit feed yet" + flag "not connected yet" | — | correcto: pantalla oculta de la navegación, backend sin endpoint de lectura | — | PASS |
| Login/Extraction | Labels, aria, role, teclado y estados de error ya presentes | — | sin cambios necesarios | build PASS | PASS |
| Render visual real en navegador | — | — | sin playwright/puppeteer en el entorno | — | NOT VERIFIED |
| Escritorio/móvil en navegador | — | — | sin navegador headless; verificación por código/CSS + tests jsdom | — | NOT VERIFIED |

- `npx ng test` (suite completa) → **11 archivos / 79 PASS**; componentes afectados → 5 archivos / 35 PASS; `npx ng build` → exit 0 (solo 2 warnings pre-existentes); `git diff --check` → exit 0; dev server `:4200` recompilado (styles.css contiene `pb-table-scroll`).
- **No se cambiaron** reglas de negocio, permisos, estados, endpoints ni contratos; sin dependencias nuevas; sin datos ficticios; sin commits.
