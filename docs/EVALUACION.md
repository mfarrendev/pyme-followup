# Plan de evaluación

## Objetivo

Determinar si el MVP reduce el trabajo manual y mejora la cobertura del seguimiento en el caso de estudio. La evaluación de la herramienta y el análisis del desarrollo asistido por IA se documentarán por separado.

## Diseño de la comparación

1. Preparar dos lotes equivalentes de 30 solicitudes ficticias cada uno, con el mismo reparto de complejidad, campos opcionales, incidencias y estados. Usar el CSV de ejemplo como referencia de formato, sin tratar sus cinco filas como una muestra suficiente.
2. Definir un proceso manual de referencia: registro en una hoja de cálculo, confirmación mediante plantilla de correo y control de vencimientos en una agenda.
3. Ejecutar las mismas tareas funcionales con el MVP. Utilizar un capturador de correo en ambos procesos.
4. Alternar el orden de las condiciones entre participantes, cuando sea posible, para reducir el efecto del aprendizaje. Si solo participa una persona, reconocer esta limitación y usar lotes equivalentes distintos.
5. Medir el tiempo activo por tarea y registrar errores e intervenciones. Separar el tiempo de espera del tiempo de trabajo.
6. Simular los vencimientos mediante un reloj controlado para comprobar contactos sin seguimiento, cierres y cambios de fecha.
7. Presentar los resultados observados, el tamaño de la muestra y las incidencias. No completar resultados con estimaciones.

Las pruebas de fallo deliberado, como un proveedor de correo caído, se ejecutarán como escenarios técnicos separados del flujo normal, para que no distorsionen de forma accidental la comparación de tiempos.

## Indicadores

| Indicador | Definición | Objetivo propuesto |
| --- | --- | --- |
| Tiempo activo por solicitud | Tiempo dedicado al registro, confirmación, consulta y seguimiento, dividido entre solicitudes procesadas. | Reducción de al menos el 30 %. |
| Reducción del tiempo | `(tiempo manual − tiempo automatizado) / tiempo manual × 100`. | Informar el valor observado; no calcular si la base es cero. |
| Cobertura del seguimiento | Solicitudes que requieren seguimiento y tienen una actuación efectiva registrada dentro del plazo / solicitudes cuyo plazo ha vencido × 100. | Al menos el 95 %. |
| Errores de registro | Solicitudes con campos incorrectos o ausentes frente al dato de referencia / solicitudes procesadas × 100. | No superar el proceso manual. |
| Puntualidad del recordatorio | Recordatorios creados dentro de los 5 minutos posteriores al vencimiento / recordatorios esperados × 100. | 100 % en pruebas con el trabajador disponible. |
| Duplicados de trabajo | Trabajos de notificación adicionales para la misma clave lógica. | Cero en los escenarios de idempotencia. |

Un aviso interno no equivale a seguimiento realizado: este requiere que el equipo registre una actuación efectiva. Las metas son hipótesis de evaluación y no garantías comerciales.

## Registro de resultados

| Métrica | Proceso manual | MVP | Diferencia | Observaciones |
| --- | --- | --- | --- | --- |
| Tiempo activo medio por solicitud | Pendiente | Pendiente | Pendiente | |
| Mediana del tiempo activo | Pendiente | Pendiente | Pendiente | |
| Cobertura del seguimiento | Pendiente | Pendiente | Pendiente | |
| Errores de registro | Pendiente | Pendiente | Pendiente | |

Se conservará un registro de tareas con condición, participante ficticio o identificador seudónimo, solicitud, inicio, fin, duración e incidencias. La puntualidad y los duplicados se informarán adicionalmente en las pruebas técnicas del MVP.

## Evaluación del desarrollo asistido

Registrar en `docs/DESARROLLO_CON_IA.md` las tareas asistidas, tiempo de interacción y revisión, fallos encontrados y cambios aceptados. Este registro describe cómo se utilizó el asistente, pero no demuestra por sí mismo un ahorro frente a desarrollar sin asistencia. Una comparación causal requeriría tareas equivalentes y condiciones de desarrollo controladas.

## Limitaciones

La muestra es pequeña y ficticia; el comportamiento real del personal, el volumen de spam y la disponibilidad del correo pueden variar. Las pruebas con tiempo simulado verifican reglas, pero no sustituyen un piloto operativo. El efecto sobre conversiones y ventas queda fuera de esta evaluación inicial.

## Pruebas del MVP

Las 20 pruebas automáticas (`make test`) verifican las reglas, no el
impacto. Una prueba que nunca se vio fallar no prueba nada, así que cada
una se midió: se puso a mano el defecto que vigila, se corrió la suite
completa (con un arnés que exige que corran las 20) y se revirtió el
cambio.

| Defecto puesto a mano | Pruebas que fallaron |
| --- | --- |
| Email sin validar | 1 de 20 (escenario 2) |
| Sin revisar la clave de envío | 1 de 20 (escenario 3) |
| La nota interna cuenta como contacto | 1 de 20 (escenario 5) |
| El contacto no reemplaza el vencimiento | 3 de 20 (escenarios 6 y 11, y la actuación desde el panel) |
| Cerrar no cancela los recordatorios | 1 de 20 (escenario 7) |
| La clave del recordatorio no incluye el vencimiento | 1 de 20 (escenario 8) |
| Reintentos sin límite | 1 de 20 (escenario 9) |
| El error permanente se reintenta | 1 de 20 |
| Exportar sin sesión | 1 de 20 (escenario 10) |
| Sin revisar la vigencia antes de enviar | 1 de 20 (escenario 11) |
| Sin exigir el token CSRF | 1 de 20 |
| CSV sin neutralizar fórmulas | 1 de 20 |
| Plantillas sin escape de HTML | 1 de 20 |
