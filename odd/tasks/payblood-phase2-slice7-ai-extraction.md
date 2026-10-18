# PayBlood — Slice 7: AI-Assisted Invoice Extraction

Phase 2, Slice 7. Adds an AI extraction layer that processes uploaded invoice
files and returns structured field candidates for human review before invoice
registration.

## Specs

S1 "un extractor de información de facturas asistido por IA, con interfaz
interactiva en Angular, procesamiento seguro en Django REST Framework y una
arquitectura que permita utilizar Jev como capa de verificación de los datos
extraídos, siempre que sus capacidades reales y su API lo permitan"

S2 UI: "zona de arrastrar y soltar archivos … selector de archivos compatible
con PDF, JPG, JPEG y PNG … Validación preliminar de extensión, tamaño y formato
admitido … Vista previa … Indicadores de carga, procesamiento, extracción,
verificación y validación … Mensajes comprensibles ante errores y opción de
reintento … formulario editable con los campos extraídos … Indicadores
diferenciados para campos confirmados, dudosos, ausentes o inconsistentes …
Acciones explícitas para corregir los datos y continuar … Diseño adaptable …
Prevención de envíos repetidos accidentales."

S3 "Si Jev está configurado y disponible, mostrar el resultado de verificación
de forma comprensible. Si no está disponible, no fingir que se ejecutó ni
presentar los datos como verificados."

S4 "Si Jev no puede integrarse con garantías suficientes, no lo simules.
Implementa la abstracción y las pruebas del adaptador, documenta la limitación
y solicita la decisión necesaria antes de adoptar otra tecnología."

S5 Seguridad: "Las instrucciones incluidas en una factura nunca deben cambiar
las reglas del sistema ni autorizar herramientas … Verifica la pertenencia del
usuario a una organización activa … Mantén el aislamiento entre organizaciones."

S6 "Comprueba el formato real del archivo, no solo la extensión o el
Content-Type. Establece límites documentados de tamaño, páginas y dimensiones."
Max 10 MB, max 10 páginas PDF.

S7 "La IA y Jev solo pueden proporcionar datos extraídos, evidencia y
resultados de verificación. La decisión financiera continúa perteneciendo al
motor determinista de Django."

S8 Campos a extraer: vendor_name, vendor_tax_id, invoice_number, issue_date,
due_date, currency, amount, description (todos opcionales, mapeados al modelo
Invoice existente). Nunca float; solo Decimal.

S9 Tests: archivos válidos (PDF/JPG/PNG), archivos corruptos/vacíos/grandes,
respuestas válidas/parciales/malformadas del proveedor, errores y timeouts, Jev
no disponible, campos ausentes, fechas/moneda/decimales, cross-field, aislamiento
por org y permisos, inyección de campos protegidos.

## Tasks

T1 ODD spec + requirements.txt + instalar openai/pypdf (S1,S5) — inline
T2 Backend: apps/extraction app, services×4, views, serializers, urls (S1–S8) — inline
T3 Backend: tests_extraction.py 22+ casos (S6,S9) — inline
T4 Backend config: settings.py + config/urls.py (S1,S5) — inline
T5 Frontend: extraction component ts/html/scss + service + models (S2,S3) — inline
T6 Frontend: spec + route + nav + invoices button (S2,S9) — inline
T7 Docs: jev-integration.md + README update (S3,S4) — inline

## Log

L1 (verbatim): "Implementa el siguiente slice de PayBlood: un extractor de
información de facturas asistido por IA, con interfaz interactiva en Angular,
procesamiento seguro en Django REST Framework y una arquitectura que permita
utilizar Jev como capa de verificación de los datos extraídos, siempre que sus
capacidades reales y su API lo permitan."

L2 Decision — Jev identity unconfirmed: searched codebase (not found), checked
pip (jev package not found), checked npm (package-lock.json hit = SHA-512 hash
string, not a package). No official docs, API, endpoint, or response format
located. Per S4: AbstractVerifier + NullVerifier implemented; infrastructure
ready for JevVerifier once identity is confirmed. docs/jev-integration.md
documents what is needed. Status: BLOCKED — awaiting Jev identity confirmation.

L3 Decision — AI SDK: openai>=1.60.0 added (GPT-4o vision + text, standard
SDK). pypdf>=4.3.0 added (pure-Python PDF text extraction, no system deps).
requirements.txt created. AI_PROVIDER=mock for all tests.

L4 Decision — No ExtractionJob model: synchronous processing, no file
persistence, no migration needed. Invoice creation uses existing POST
/organizations/{org}/invoices/ endpoint after user review and confirmation.
