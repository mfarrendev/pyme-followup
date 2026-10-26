# Especificación funcional y técnica

## Requisitos funcionales

| ID | Requisito | Criterio de aceptación |
| --- | --- | --- |
| RF-01 | Recibir una solicitud desde un formulario. | Nombre, email y descripción son obligatorios; una entrada inválida no genera registros ni envíos. |
| RF-02 | Guardar la solicitud y su origen. | Se asignan identificador, fecha UTC, estado inicial, responsable y vencimiento; el origen desconocido se registra como tal. |
| RF-03 | Confirmar la recepción. | Se crea un trabajo de correo asociado a la solicitud y el resultado queda registrado. |
| RF-04 | Mostrar un panel privado. | Un usuario autenticado puede filtrar por estado, responsable, origen y vencimiento. |
| RF-05 | Registrar actuaciones. | Una actuación guarda autor, fecha, tipo y nota; puede establecer la próxima acción. |
| RF-06 | Recordar seguimientos vencidos. | El proceso periódico crea un recordatorio interno por solicitud y vencimiento, sin duplicarlo en ejecuciones sucesivas. |
| RF-07 | Cerrar oportunidades. | Una oportunidad ganada o perdida deja de producir recordatorios pendientes. |
| RF-08 | Exportar resultados. | El CSV permite calcular los indicadores definidos en el plan de evaluación. |
| RF-09 | Gestionar errores de correo. | Un fallo queda visible; se aplican reintentos limitados y se informa al responsable cuando se agotan. |

## Estados y reglas

Estados de una solicitud: `nueva`, `contactada`, `presupuesto_enviado`, `ganada` y `perdida`.

Transiciones permitidas:

- `nueva` → `contactada` o `perdida`.
- `contactada` → `presupuesto_enviado`, `ganada` o `perdida`.
- `presupuesto_enviado` → `ganada` o `perdida`.
- `ganada` y `perdida` son estados finales en el MVP.

Una solicitud nueva tiene un vencimiento inicial a las 48 horas naturales. Al registrar un contacto efectivo o un presupuesto enviado, el usuario deberá indicar la siguiente fecha de seguimiento o cerrar la oportunidad. Una nota interna por sí sola no cuenta como contacto efectivo ni elimina el vencimiento.

El proceso periódico comprueba vencimientos cada 5 minutos. Tras crear el recordatorio, lo marca como generado para ese vencimiento. Una nueva fecha permite un nuevo recordatorio. Justo antes de procesarlo, vuelve a comprobar el estado y la fecha actuales para evitar avisos que hayan quedado obsoletos.

El origen de campaña es informativo. No se atribuyen ventas a un canal con certeza cuando faltan datos o el cliente ha utilizado varios canales.

## Modelo de datos propuesto

| Entidad | Campos principales |
| --- | --- |
| Usuario | ID, nombre, email interno, hash de contraseña, activo. |
| Solicitud | ID, clave de envío, nombre, email, teléfono opcional, descripción, origen, UTM source/medium/campaign opcionales, estado, responsable, fecha de creación, próxima acción, fecha de cierre. |
| Actuación | ID, solicitud, usuario, tipo, nota, fecha, indicador de contacto efectivo. |
| Trabajo de notificación | ID, solicitud, tipo, vencimiento asociado, clave única, estado, intentos, próxima ejecución, último error, fecha de envío, ID del proveedor si existe. |

Estados de los trabajos: `pendiente`, `en_proceso`, `enviado`, `fallido` y `cancelado`. Las fechas se almacenan en UTC y se presentan en la zona horaria configurada para la empresa.

## Consistencia y entrega de correo

La solicitud y su trabajo de confirmación se guardarán en la misma transacción. Una clave única de envío evita que un doble clic con la misma clave cree dos solicitudes. Una nueva solicitud del mismo email puede ser legítima y no se descartará automáticamente.

Los recordatorios tendrán una clave única formada por solicitud, tipo y vencimiento. El MVP ejecutará un único trabajador y reclamará las tareas de forma transaccional. Un trabajo bloqueado tendrá un tiempo límite y una vía de recuperación.

Se permitirán hasta tres intentos totales, con reintentos a 1 y 5 minutos después de un fallo. Las credenciales inválidas y otros errores permanentes requerirán intervención. Se registrará el fallo sin guardar credenciales ni cuerpos completos con datos personales en los logs.

SMTP puede aceptar un mensaje y perderse la confirmación de entrega al proceso. Por ello no se promete entrega exactamente una vez: ante un resultado ambiguo se señalará para revisión, evitando reintentos ciegos. Cuando el proveedor lo permita se utilizarán claves de idempotencia.

## Seguridad y privacidad

- El formulario es público; el panel, las exportaciones y las operaciones internas requieren autenticación.
- Las contraseñas se almacenan mediante un hash apropiado y las sesiones usan cookies seguras en producción.
- Se validan entradas, se escapan textos en la interfaz y se protegen formularios privados frente a CSRF.
- Se limita la frecuencia del formulario público para reducir spam.
- Los secretos se configuran mediante variables de entorno y quedan fuera del repositorio.
- Las exportaciones CSV neutralizan valores que puedan interpretarse como fórmulas.
- Se recogen solo los datos necesarios y se define un procedimiento de borrado y conservación antes del piloto real.

## Escenarios de aceptación

1. Una solicitud válida aparece una sola vez y genera un trabajo de confirmación.
2. Una solicitud sin email válido muestra errores y no genera trabajos.
3. Repetir el mismo envío con la misma clave no crea duplicados.
4. Una solicitud sin contacto efectivo genera un recordatorio al vencer.
5. Registrar una nota interna no evita ese recordatorio.
6. Registrar un contacto y una próxima acción sustituye el vencimiento anterior.
7. Cerrar una oportunidad cancela sus recordatorios pendientes.
8. Ejecutar el proceso dos veces no duplica el trabajo del mismo vencimiento.
9. Un fallo de correo respeta el límite de intentos y queda visible.
10. Una persona sin sesión no puede consultar ni exportar contactos.
11. Un cambio de estado mientras hay un recordatorio pendiente impide un aviso obsoleto.

Las pruebas temporales utilizarán un reloj controlado; no será necesario esperar 48 horas reales. Los envíos se comprobarán en un capturador de correo local.
