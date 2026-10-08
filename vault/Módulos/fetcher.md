# fetcher

**Qué hace:** por cada radicado consulta la API de [[API Rama Judicial]] y devuelve las actuaciones, o un resultado tipificado si algo falla.

## Peticiones
1. Búsqueda por radicado, siempre con `SoloActivos=false`.
2. Actuaciones de **cada proceso** que devuelva la búsqueda (un radicado puede tener varios), unidas sin duplicar por `idRegActuacion`.
3. Todas las páginas de actuaciones, guiado por el campo `cant` (total del proceso), con tope de 20.
4. Detalle (fecha de replicación): apagado por defecto (`consultar_detalle = false`) para ahorrar una petición por radicado.

## Cómo se porta con el portal
- Se identifica con un User-Agent propio. El portal rechaza con 403 el de `requests`.
- Pausa de 1,5 s entre peticiones (`pausa_peticiones_segundos`).
- Errores de red o HTTP: 3 reintentos con espera creciente.
- 403 o 429: es el bloqueo por cuota. Espera 60, 120 y 240 s y reintenta. Si persiste, devuelve `bloqueo=True` y [[main]] pausa el ciclo. Ver [[Operación y límites del portal]].
- Un 404 solo es "sin actuaciones" si el cuerpo trae el mensaje `No se encontraron Actuaciones`. Cualquier otro 404 es falla del portal.

## Resultados
| Estado | Cuándo |
|---|---|
| Exitosa | Respuesta correcta, con o sin actuaciones |
| Fallida | Radicado inválido (no cuenta para R5), sin resultados o portal caído (cuentan) |
| Error | La respuesta llegó con forma inesperada, incluida una clave renombrada. Dispara la alerta de posible cambio en la API |

## Privacidad
`sujetosProcesales` trae nombres de personas naturales. Se descarta aquí, antes de que llegue al resto del código.

**Es el único módulo que conoce la Rama Judicial.** Si el portal cambia, solo se toca este archivo.

**Depende de:** requests. Usado por [[main]].
