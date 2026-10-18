# PayBlood — Corrección de hallazgos críticos y preparación de despliegue

## Header
Fase autorizada y limitada: resolver los hallazgos de la auditoría y preparar
configuración de producción, sin publicar código ni desplegar. Conservar los
cambios locales, no hacer reset/clean, no commit/push/deploy, no imprimir
secretos, no eliminar `.env.example` local, no cambiar arquitectura ni añadir
dependencias sin justificación, mantener el remoto `origin` existente.

## Specs
- S1. Inspeccionar git status/rama/HEAD/diff antes de actuar; conservar cambios;
  sin reset/clean; sin commit/push/deploy; sin imprimir secretos; mantener origin.
- S2. Corregir secreto en `.env.example`: sustituir cualquier clave real por
  placeholder vacío/ficticio (incl. OPENROUTER_API_KEY), confirmar que no queda
  credencial real, retirar `.env.example` del seguimiento conservando el local,
  comprobar el índice. Autorizado el cambio de índice SOLO para `.env.example`;
  no stagear otros archivos. No publicar ni push.
- S3. `.gitignore`: excluir backend/.diagtmp/ y backendas sqlite .bak (patrones
  de respaldo locales verificados), sin eliminar archivos; verificar con
  git check-ignore.
- S4. Frontend prod: quitar apiBaseUrl "http://localhost:8000" de producción,
  reutilizando el mecanismo de Angular existente; permitir configurar la URL
  real mediante el mecanismo que el proyecto soporte (no inventar dominio; no
  meter secretos en el bundle; conservar entorno dev). Si la URL real no
  existe, dejar el valor documentado como pendiente.
- S5. Backend Railway: sólo ajustes locales para un arranque seguro (comando de
  arranque compatible, ALLOWED_HOSTS, CORS/CSRF, DATABASE_URL postgres si
  soporta, DEBUG=False). No instalar Gunicorn/WhiteNoise sin verificar.
  No crear servicios ni migrar.
- S6. Rotación de credencial OpenRouter: NO imprimir la clave; indicar que debe
  revocarse y rotarse por el proveedor; no marcarla completada sin confirmación
  verificable del usuario/proveedor; la app usará la nueva vía config privada.
- S7. Validaciones: git diff --check, git status, check-ignore, manage.py check,
  makemigrations --check --dry-run, tests backend aislado, suite frontend, build
  producción, inspección del bundle por "localhost:8000". Sin migrar bases.
- S8. Informe: archivos modificados y motivo; confirmar .env.example conservado
  local y fuera del índice; nada publicado; estado git/índice; .gitignore;
  config prod y valores pendientes; tests/build; riesgos (rotación OpenRouter
  sin confirmar); próximo paso.

## Tasks
| ID | Spec | Route | Commit |
| --- | --- | --- | --- |
| T1 | S1 | inspección git + doc ODD | — (worktree only) |
| T2 | S2 | .env.example: placeholder + git rm --cached | — (índice sólo .env.example) |
| T3 | S3 | .gitignore: .diagtmp, .bak | — |
| T4 | S4 | environment.ts prod (sin localhost) | — |
| T5 | S5 | docs/backend-railway config | — |
| T6 | S6 | doc rotación OpenRouter | — |
| T7 | S7 | validaciones | — |
| T8 | S8 | informe + detenerse | — |

## Log
- L1: brief del usuario autorizando la corrección limitada; repo remoto
  https://github.com/IvanPalmar0207/30xChallenge.git; sin commit/push/deploy;
  corregir .env.example (placeholder + retirar del seguimiento conservando
  local), .gitignore (.diagtmp, .bak), frontend prod sin localhost (sin inventar
  dominio), preparar backend Railway, no instalar Gunicorn/WhiteNoise sin
  verificar, rotar OpenRouter sin imprimir; validar y detenerse.
- L2: preflight — main @ 7c48773; 33 M / 1 D / 53 ??; nada staged; origin
  configurado correctamente; la OPENROUTER_API_KEY real (working-tree len 73)
  NO está en HEAD (HEAD ai-key vacía, sin OPENROUTER_API_KEY) -> se corrige sin
  reescribir historial.
