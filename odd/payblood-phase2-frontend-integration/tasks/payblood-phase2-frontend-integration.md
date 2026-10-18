# PayBlood — Phase 2: Frontend Integration (Dashboard, Vendors, Policies)

Reference: `docs/implementation-contract.md` (unchanged invariants); slices 1–7 ODD specs; backend contract in `backend/apps/organizations/{views,serializers,permissions,urls}.py`.

Decision (user, this session): Dashboard implemented as a real-data summary using existing endpoints only; **no new summary endpoint** is created now.

## Specs

- **S1 — Dashboard, datos reales**: "utiliza `/organizations/`, `/invoices/` y `/policies/` únicamente para obtener datos que el usuario esté autorizado a consultar. Implementa indicadores sencillos que puedan calcularse correctamente a partir de las respuestas disponibles, como cantidades de facturas o políticas, solo si los datos y filtros del backend permiten hacerlo de forma fiable. No inventes métricas financieras, estados ni reglas de negocio. Si un dato no puede calcularse con seguridad, omítelo y documenta la limitación. Incluye estados de carga, errores, ausencia de datos y navegación a Vendors e Invoices. Evita solicitudes redundantes y respeta el aislamiento por organización."
- **S2 — Vendors**: "Verifica listado, creación, edición y activación/desactivación únicamente si esas operaciones están soportadas. Respeta la normalización del identificador tributario, los campos permitidos y las restricciones del backend."
- **S3 — Policies**: "integra las operaciones que realmente admite el backend, respetando los permisos y el contrato existente. No inventes reglas, umbrales ni capacidades que no estén implementadas. El motor de políticas debe seguir siendo responsable de la evaluación financiera."
- **S4 — Calidad**: "sigue las métricas de aceptación existentes para Vendors y Policies. Para Dashboard, como no existe un contrato explícito de métricas, define criterios mínimos y verificables de presentación de datos, navegación, estados de carga/error y aislamiento, y documéntalos claramente como criterios nuevos propuestos, sin presentarlos como requisitos preexistentes."
- **S5 — Pruebas y límites**: "ejecuta las pruebas relevantes, el build de producción y las regresiones. Distingue PASS, FAIL, BLOCKED y NOT VERIFIED, y aporta los comandos y resultados reales. No agregues endpoints ni modifiques el contrato backend salvo que encuentres un bloqueo concreto… No alteres la base de desarrollo, no hagas staging, commits ni push."
- **S6 — Contrato backend verificado (reads)**: listas sin paginación (`REST_FRAMEWORK` sin `DEFAULT_PAGINATION_CLASS`); vendor: `GET/PATCH /api/v1/organizations/{org}/vendors/` y `/vendors/{id}/`, `POST /vendors/` (crear), `POST /vendors/{id}/activate|deactivate/`; policy: `GET/POST /policies/`, `GET /policies/{id}/` (sin update/delete); campos exactos de `VendorSerializer`, `PolicySerializer`; `tax_id` normalizado strip+upper por backend; status no escribible por PATCH; creación de política desactiva la versión anterior (una activa por org).

## Dashboard: criterios nuevos propuestos (no preexistentes)

No existe un contrato explícito de métricas de Dashboard en documentos previos; estos criterios mínimos y verificables se proponen con esta implementación y NO se presentan como requisitos preexistentes:

- **D1 — Datos reales**: cada indicador se calcula de las respuestas de `/invoices/` y `/policies/` (listas sin paginar) para la organización activa de la sesión; no hay métricas inventadas (sin totales financieros: las facturas pueden mezclar monedas y la API no ofrece agregados).
- **D2 — Conteos simples**: total de facturas, conteos por estado (received, pending_approval, approved, blocked, escalated, rejected — los seis estados reales del backend), facturas que requieren atención (blocked + escalated + pending_approval), versión de política activa y número de versiones.
- **D3 — Política activa**: muestra versión activa con sus reglas (currencies, max_amount, escalation, required data); sin política activa muestra el estado honesto (no_active_policy => escalada, nunca aprobada).
- **D4 — Navegación**: enlaces reales a Vendors (`/app/vendors`) e Invoices (`/app/invoices`), y hacia la lista de políticas/invoices cuando aplica.
- **D5 — Estados de carga/error/ausencia**: loading, no-organization, forbidden (403), error con retry, y estados vacíos por sección (sin facturas / sin política).
- **D6 — Aislamiento y eficiencia**: toda lectura usa el organization_id de la membresía activa (el backend aísla); exactamente dos requests paralelos por carga (invoices + policies), sin llamadas redundantes a `/organizations/` (la identidad ya viene de la sesión).

## Tasks

| ID | Specs | Task | Estado |
|---|---|---|---|
| T1 | S2, S4, S6 | Servicio y página de Vendors: listado, alta, edición (legal_name/tax_id), activar/desactivar con gating FINANCE_ADMIN, estados loading/empty/forbidden/error, normalización visual tax_id, spec vitest. | done (spec 9/9 PASS, job-61) |
| T2 | S3, S4, S6 | Servicio y página de Policies: listado de versiones, lectura, alta (FINANCE_ADMIN) con campos reales y semántica one-active, estados, spec vitest. | done (spec 8/8 PASS, job-63) |
| T3 | S1, S4, S6 | Dashboard: conteos reales (invoices totales y por estado, policies activas/versiones), política activa, navegación a Vendors e Invoices, estados de carga/error/ausencia, criterios nuevos propuestos documentados, spec vitest. | done (spec 7/7 PASS, job-64) |
| T4 | S5 | Correr specs vitest, build de producción, `git diff --check`, regresión backend (solo lectura si aplica), informe final con PASS/FAIL/BLOCKED/NOT VERIFIED. | pending |

## Log

- L1 (user, verbatim): request en Español: implementar incrementalmente Dashboard, Vendors y Policies con endpoints reales existentes; Dashboard con `/organizations/`, `/invoices/`, `/policies/` únicamente, indicadores sencillos, sin métricas inventadas, estados de carga/error/ausencia y navegación a Vendors e Invoices; Vendors con listado, creación, edición y activación/desactivación solo si el backend lo soporta, respetando normalización de tax_id; Policies solo operaciones soportadas, sin reglas inventadas; calidad con métricas existentes para Vendors/Policies y criterios nuevos propuestos para Dashboard; pruebas relevantes + build + regresiones con PASS/FAIL/BLOCKED/NOT VERIFIED; sin endpoints nuevos ni cambios de contrato; sin staging/commits/push; informe final con criterios, archivos modificados, resultados, limitaciones y estado de Git.
- L2 (decision, user): "Prefiero implementar el Dashboard como un resumen basado en datos reales, utilizando los endpoints existentes, sin crear por ahora un endpoint nuevo de resumen."
