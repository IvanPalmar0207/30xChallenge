# PayBlood — Cuentas demo, README y verificación de permisos

## Resumen

Preparar PayBlood para evaluación externa: cinco cuentas identificables (superadmin existente + FINANCE_ADMIN, OPERATOR, APPROVER, AUDITOR en `Demostracion 30X`), README profesional en español con credenciales demo públicas, y verificación de permisos de cada rol en producción.

URLs: frontend https://payblood.netlify.app · backend https://payblood-production.up.railway.app

## Specs

- S1: Conservar superadmin `palmar.ivan0205@gmail.com` sin tocar su contraseña ni privilegios.
- S2: Crear solo las cuentas que falten: FINANCE_ADMIN, OPERATOR, APPROVER, AUDITOR en `Demostracion 30X`, activas, sin superuser/staff, sin permisos globales, membresía única, únicamente su rol.
- S3: Contraseñas demo fuertes, únicas, exclusivas para la demo, publicadas en el README (repo público, decisión explícita del usuario), nunca en código/logs/migraciones.
- S4: Verificar el login y los permisos reales de cada cuenta contra el backend de producción (operación permitida y denegada por rol), sin desactivar controles y sin pruebas destructivas.
- S5: README.md final en español con presentación, arquitectura+diagrama Mermaid, funcionalidades, tabla de roles, acceso a la demo, endpoints, instalación local, pruebas, despliegue, limitaciones.
- S6: Revisión final: `git diff --check`, sin commits/push/deploys, lista exacta de archivos modificados.
- S7: No publicar contraseña ni tokens del superadmin; solo su correo y descripción. No publicar `.env.example`.

## Tareas

- T1 (S2,S3): Crear las 4 cuentas demo en producción vía la API real (users/ + invite/ + set-password/) con contraseñas únicas seguras.
- T2 (S4): Verificar login y permisos de cada cuenta (me/, operación permitida, operación denegada).
- T3 (S5): Reescribir README.md en español con todas las secciones y la tabla de credenciales demo.
- T4 (S6): Revisión final de Git, diff --check e informe.

## Log

- L1: Solicitud de preparación de cuentas de demostración y documentación final (usuario).
- L2: Aclaración: publicar credenciales de las 4 cuentas demo en el README; superadmin sin contraseña.
- L3: Inspección: repo público; org demo sin datos reales; un solo usuario (superadmin); roles confirmados en código.
