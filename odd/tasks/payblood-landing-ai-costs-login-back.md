# PayBlood — landing AI costs + login back navigation

## Header
Tarea de cierre del frontend de PayBlood: una sección de estimación de costos de IA en la
landing (antes del CTA/footer), un botón secundario «Volver al inicio» en el login que
navegue a la landing, y el fix del selector de archivos de la página de upload (reportado
por el usuario: «el botón upload invoice no sirve»: doble disparo de openFileDialog por el
label dentro de la zona clicable). Solo frontend; sin staging, commits, push, migraciones ni
cambios en la DB de desarrollo.

## Specs
- S1. Sección «¿Cuánto cuesta automatizar tus facturas?» antes del final de la landing
  (entre la sección Engine y el CTA), coherente visualmente (variables --pb-*), responsive.
- S2. Controles: facturas/día, días de operación al mes, costo estimado de IA por factura
  (USD, editable, supuesto ilustrativo marcado, no tarifa real), % de reprocesamiento opcional.
- S3. Resultados en vivo con fórmulas transparentes: facturas mensuales = facturas/día ×
  días/mes; costo mensual = facturas_mes × costo_factura × (1 + %reprocesamiento/100);
  costo anual = costo mensual × 12; costo por factura ajustado = costo_factura × (1 + %/100).
- S4. Validación: entradas negativas/NaN → mensaje de error, sin resultados engañosos.
- S5. Honestidad: se dice que el cálculo es del costo del proveedor de IA, que NO incluye
  infraestructura/almacenamiento/BD/monitoreo, que no hay costos medidos reales todavía, que
  la calculadora no llama a ningún proveedor ni usa claves API, y que distintas facturas
  pueden tener distinto consumo (escenario estimado).
- S6. Login: botón secundario «Volver al inicio» debajo del botón de ingresar que navega a
  la landing pública (`/`) con routerLink de Angular, sin disparar el submit del formulario
  y sin tocar validaciones/mensajes/permisos de login.
- S7. Fix upload: un solo disparador de openFileDialog por clic (remover disparos duplicados
  del label/botón internos), manteniendo el flujo de drag & drop, teclado y aria intactos.
- S8. Regresión: tests de la calculadora (límites, cero, decimales, reprocesamiento), test
  de navegación login→landing, suite completa del frontend, build de producción y
  `git diff --check`. Sin cambios de backend ni dependencias nuevas.

## Tasks
| ID | Spec | Route | Commit |
| --- | --- | --- | --- |
| T1 | S1-S5 | inline | — (sin commits; worktree only) |
| T2 | S6 | inline | — |
| T3 | S7 | inline | — |
| T4 | S8 | inline | — |

## Log
- L1: brief del usuario: sección de costos IA pre-footer con calculadora (facturas/día, días/mes,
  costo/factura USD editable ilustrativo, % reprocesamiento), fórmulas transparentes, exactitud
  (no inventar precios, no costo total del producto, sin llamar proveedores ni claves, sin tocar
  el motor de políticas); botón «Volver al inicio» debajo del login; pruebas + build + diff-check +
  informe; sin staging/commits/push ni cambios de DB.

### Resultado — decision: keep the whole app in english

- On user request, the whole frontend stays in English (the app was already in
  English except the new section and the login link). Final strings:
  - Landing section title: «How much does it cost to automate your invoices?»
    with inputs "Invoices processed per day", "Operating days per month",
    "Estimated AI cost per invoice (USD)", "Reprocessing percentage (optional)",
    results "Estimated monthly invoices", "Estimated monthly AI cost",
    "Estimated annual cost", "Estimated cost per invoice (with reprocessing)",
    formulas in English and the illustrative-assumption fine print in English.
  - Login secondary button: «Back to home» (navigates to `/` via routerLink).
  - Also translated to English the remaining Spanish leftovers: extraction
    extractDisabledReason hints and the file-input fallback copy, plus a
    Spanish word in the logo comment.
- Verification: ai-cost + login + extraction specs 26 PASS; full suite 13 files
  / 94 PASS; `npx ng build` exit 0; `git diff --check` exit 0; dev server
  serves the English strings (main.js contains the new title and "Back to
  home"). No staging, commits, push, DB writes or backend changes.
