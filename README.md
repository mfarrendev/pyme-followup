# Pyme FollowUp

**Automatización del seguimiento de clientes potenciales en pequeñas y medianas empresas con ayuda de Codex.**

Propuesta de proyecto para reducir el trabajo administrativo asociado a las solicitudes de presupuesto y mejorar la continuidad del seguimiento comercial de los contactos obtenidos mediante acciones de marketing.

> Estado: definición y diseño del proyecto. Este repositorio contiene la documentación para desarrollar y evaluar un MVP; todavía no incluye una aplicación ejecutable.

## Resumen ejecutivo

Las pymes de servicios suelen recibir consultas a través de formularios, campañas y otros canales digitales. Cuando estas consultas se gestionan con correos, notas o archivos dispersos, resulta difícil saber quién debe responder y qué oportunidades siguen pendientes.

Pyme FollowUp propone centralizar las solicitudes recibidas mediante un formulario y automatizar tres tareas: registrar el contacto, confirmar la recepción por correo electrónico y recordar al responsable los seguimientos pendientes. Un panel permitirá consultar y actualizar el estado de cada oportunidad.

Como caso de estudio se utilizará una empresa ficticia de reformas. El mismo flujo puede adaptarse a agencias, academias, talleres y otros negocios que trabajan mediante presupuestos.

## Problema y pregunta de investigación

El problema que se aborda es la falta de un proceso uniforme para gestionar las oportunidades generadas por marketing. Registrar información a mano y depender de la memoria del equipo puede provocar retrasos, duplicados y contactos sin seguimiento.

**Pregunta principal:** ¿en qué medida una herramienta desarrollada con ayuda de Codex puede reducir el tiempo de gestión y aumentar el porcentaje de solicitudes de presupuesto que reciben seguimiento en una pyme?

La mejora de las ventas se considera un posible efecto posterior. El MVP se evaluará sobre el funcionamiento y la eficiencia del proceso, sin atribuirle incrementos de ventas no demostrados.

## Objetivos

### Objetivo general

Diseñar y evaluar una automatización que permita a una pyme registrar, organizar y dar seguimiento a sus solicitudes de presupuesto con menos intervención manual.

### Objetivos específicos

- Centralizar las solicitudes y asignar un responsable a cada una.
- Confirmar automáticamente la recepción de las solicitudes válidas.
- Generar recordatorios internos cuando venza el plazo de seguimiento.
- Facilitar la consulta del estado y del historial de cada oportunidad.
- Comparar el tiempo de gestión y la cobertura del seguimiento frente a un proceso manual.
- Documentar las aportaciones de Codex y las correcciones realizadas durante el desarrollo.

## Usuarios y caso de uso

| Usuario | Necesidad |
| --- | --- |
| Persona interesada | Solicitar un presupuesto y recibir una confirmación. |
| Responsable comercial | Saber qué solicitudes atender y registrar el resultado. |
| Responsable de marketing o gerencia | Consultar el origen de las solicitudes y el cumplimiento del seguimiento. |

Ejemplo: una persona llega desde una campaña a la web de una empresa de reformas y solicita presupuesto. El sistema registra la consulta, conserva su origen de campaña, envía una confirmación y establece un plazo de seguimiento. Si el equipo no registra una actuación antes del vencimiento, recibe un recordatorio interno.

## Flujo de automatización

```mermaid
flowchart TD
    A[Formulario de solicitud] --> B{Datos válidos}
    B -->|No| C[Mostrar errores y solicitar corrección]
    B -->|Sí| D[Registrar solicitud y asignar responsable]
    D --> E[Programar confirmación y vencimiento]
    E --> F[Enviar confirmación al cliente]
    E --> G[Mostrar solicitud en el panel]
    G --> H{¿Seguimiento registrado antes del vencimiento?}
    H -->|Sí| I[Actualizar estado y próxima acción]
    H -->|No| J[Crear recordatorio interno]
    J --> I
    I --> K{¿Oportunidad cerrada?}
    K -->|Sí| L[Cancelar recordatorios pendientes]
    K -->|No| G
```

El recordatorio inicial vencerá 48 horas naturales después de la recepción. Es una regla provisional para el caso de estudio, configurable según el negocio. La confirmación automática no cuenta como atención comercial ni como seguimiento realizado.

## Alcance del MVP

**Incluye:**

- Formulario web con validación de datos.
- Registro centralizado de solicitudes y origen de campaña, cuando esté disponible.
- Asignación a un responsable predeterminado y reasignación manual.
- Confirmación por correo electrónico.
- Panel privado con búsqueda, filtros y actualización de estados.
- Registro manual de actuaciones y próxima fecha de seguimiento.
- Recordatorios internos, historial y registro de errores de envío.
- Indicadores básicos y exportación CSV para evaluación.

**Fuera del MVP:**

- Envío de campañas comerciales masivas o seguimientos automáticos al cliente.
- Integración con WhatsApp, CRM externos o plataformas de anuncios.
- Generación automática de presupuestos o valoración económica de trabajos.
- Predicción de ventas, clasificación mediante aprendizaje automático y gestión multempresa.

## Papel de Codex y de la IA

Codex se utilizará como asistente de desarrollo para convertir los requisitos en código, proponer el modelo de datos, implementar conexiones, generar pruebas y ayudar a corregir errores. Las decisiones, revisiones y validaciones corresponderán a la persona responsable del proyecto.

La automatización funcionará con reglas y tareas programadas; no necesita consultar un modelo de IA durante su uso. El componente de IA del proyecto es el desarrollo asistido por Codex. Incorporar un modelo para redactar mensajes sería una ampliación posterior con una evaluación propia.

Se mantendrá una [bitácora de uso de Codex](docs/USO_DE_CODEX.md) para registrar las tareas, las propuestas aceptadas y las correcciones necesarias. No se afirmará que Codex redujo el tiempo de desarrollo sin disponer de una comparación válida.

## Arquitectura propuesta

| Componente | Propuesta | Función |
| --- | --- | --- |
| Backend | Python y FastAPI | Validación, API y reglas del proceso. |
| Interfaz | HTML, Jinja2 y Bootstrap | Formulario público y panel privado. |
| Base de datos | SQLite para la demostración | Solicitudes, actuaciones y trabajos pendientes. |
| Proceso periódico | Comando ejecutado por cron cada 5 minutos | Envíos y comprobación de vencimientos. |
| Correo | Capturador local en pruebas; proveedor SMTP en piloto | Confirmaciones y recordatorios internos. |
| Pruebas | Pytest | Verificación de reglas y escenarios de fallo. |

La arquitectura se ha elegido para limitar el coste y la complejidad del prototipo. Un despliegue con mayor concurrencia requeriría revisar la base de datos y el procesamiento de tareas.

Consulta la [especificación funcional y técnica](docs/ESPECIFICACION.md) para conocer entidades, estados y reglas.

## Metodología y planificación

Estimación orientativa para una persona, ajustable según experiencia y disponibilidad:

| Semana | Trabajo | Entregable |
| --- | --- | --- |
| 1 | Analizar el proceso manual, definir requisitos y preparar datos ficticios. | Flujo base, datos y criterios de aceptación. |
| 2 | Implementar formulario, persistencia y panel privado. | Registro y gestión de solicitudes. |
| 3 | Implementar confirmaciones, recordatorios y tratamiento de errores. | Flujo automático verificable. |
| 4 | Ejecutar pruebas y evaluación comparativa; documentar resultados. | Demostración e informe de evaluación. |

## Evaluación

Se comparará un proceso manual con el automatizado mediante tareas equivalentes y datos ficticios. Se medirán el tiempo activo de gestión, la cobertura del seguimiento, los errores de registro y la puntualidad de los recordatorios.

Como metas de evaluación se proponen una reducción del 30 % del tiempo activo de gestión y una cobertura del seguimiento de al menos el 95 %. **Son objetivos por validar, no resultados obtenidos.**

El diseño de la comparación, las fórmulas y las limitaciones están en el [plan de evaluación](docs/EVALUACION.md).

## Datos y uso responsable

La demostración utilizará exclusivamente contactos ficticios y un servicio de captura de correo, sin enviar mensajes a direcciones reales. Los datos de ejemplo están en [examples/solicitudes.csv](examples/solicitudes.csv).

Para un piloto real deberán definirse el acceso autorizado, el aviso de privacidad, la base jurídica aplicable y el plazo de conservación. Las comunicaciones sobre una solicitud se separarán de la suscripción a publicidad; pedir un presupuesto no se interpretará como consentimiento para campañas comerciales.

## Entregables y criterio de finalización

El proyecto se considerará completado cuando se entregue una aplicación ejecutable con instrucciones de instalación, el flujo de automatización validado, las pruebas de aceptación y un informe con los resultados medidos. Este repositorio documenta la propuesta inicial que guiará ese desarrollo.

## Estructura del repositorio

```text
pyme-followup/
├── README.md
├── docs/
│   ├── ESPECIFICACION.md
│   ├── EVALUACION.md
│   └── USO_DE_CODEX.md
└── examples/
    └── solicitudes.csv
```

## Próximos pasos

1. Validar el flujo con una pyme o con el caso ficticio propuesto.
2. Implementar el MVP según los criterios de aceptación.
3. Probar el sistema con datos y correo de demostración.
4. Ejecutar la comparación y documentar las conclusiones.
