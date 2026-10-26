# Bitácora de desarrollo asistido por IA

## Finalidad

Documentar de forma verificable cómo se usa un asistente de IA en el desarrollo y qué trabajo requiere revisión humana. No introducir datos reales de clientes, contraseñas ni claves de proveedores en las instrucciones.

## Registro por tarea

| Campo | Contenido que debe registrarse |
| --- | --- |
| Fecha e identificador | Referencia de la tarea y del commit cuando exista. |
| Objetivo | Problema concreto y requisito relacionado. |
| Instrucción | Petición realizada, sin información sensible. |
| Propuesta del asistente | Resumen del código o documentación sugerida. |
| Revisión humana | Errores, decisiones y ajustes necesarios. |
| Validación | Pruebas ejecutadas y resultado observado. |
| Tiempo | Interacción, revisión y corrección, registrado por separado. |
| Resultado | Aceptado, modificado o descartado. |

## Ejemplos de instrucciones para la implementación

### Formulario y persistencia

> Implementa RF-01 y RF-02 según docs/ESPECIFICACION.md. Valida los campos en el servidor, conserva las fechas en UTC y utiliza una clave de envío única. Añade pruebas de entradas inválidas y repetición de la misma solicitud.

### Recordatorios

> Implementa el proceso periódico según la especificación. Usa un reloj inyectable para probar vencimientos y una restricción única por solicitud, tipo y vencimiento. Comprueba cierres y cambios de fecha antes de procesar cada recordatorio.

### Revisión

> Revisa el cambio frente a los criterios de aceptación. Identifica posibles pérdidas o duplicados de trabajos, acceso a contactos sin autenticación y exposición de datos en los logs. Explica los hallazgos con referencias al código y propón correcciones verificables.

## Criterio de uso

Cada cambio debe entenderse y revisarse antes de incorporarlo. Las salidas del asistente son propuestas: el informe final distinguirá el código generado, los ajustes humanos y las comprobaciones realmente realizadas.

## Registro

### MVP completo (2026-10-26)

| Campo | Contenido |
| --- | --- |
| Objetivo | Implementar el MVP según `docs/ESPECIFICACION.md`, con los once escenarios de aceptación como pruebas. |
| Asistente | Claude Code. La especificación original preveía Codex; la implementación se hizo con Claude Code. |
| Propuesta | Servicio de reglas, web FastAPI, trabajador para cron, envío de correo con captura para la demo, y 20 pruebas. |
| Revisión y correcciones | Las pruebas encontraron dos errores en la primera versión: la conexión a SQLite se abría en un hilo y se usaba en otro (8 pruebas fallaban), y el cliente de pruebas pedía `httpx2`. Ambos se corrigieron antes de entregar. |
| Validación | 20 pruebas en verde. Cada una se midió poniendo el defecto a mano (tabla en `docs/EVALUACION.md`, § Pruebas del MVP). |
| Pendiente | Revisión humana completa del código, y la evaluación comparativa con el proceso manual. |
