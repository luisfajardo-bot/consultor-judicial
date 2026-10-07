# Reglas de negocio

Tomadas del campo 6 de la spec inicial. Quién implementa cada una está entre paréntesis.

| Regla | Qué dice | Módulo |
|---|---|---|
| R1 | Una actuación con `idRegActuacion` no guardado es POSIBLE NOVEDAD. Se reportan todas las nuevas, no solo la última | [[comparator]] |
| R2 | Primera consulta de un radicado: se guarda como referencia, sin alerta | [[comparator]] |
| R3 | Sin resultados: NO VERIFICADO con motivo "sin resultados". Nunca se elimina de la lista | [[comparator]] |
| R4 | Captcha, bloqueo o error: reintentos espaciados, luego NO VERIFICADO con motivo. Número de reintentos pendiente con Sistemas | [[fetcher]] |
| R5 | Si falla más del X % del ciclo, se detiene y avisa "fuente no disponible". X pendiente con Sistemas | [[main]] |
| R6 | Una actuación alerta una sola vez. Las Descartadas no se repiten | [[store]] |
| R7 | Se consulta por radicado, nunca por nombre de parte | [[loader]] |
| R8 | Cada ciclo deja bitácora. Nada se borra | [[store]] |
| R9 | La herramienta nunca escribe en el cuadro oficial ni envía nada fuera del equipo jurídico | [[loader]], [[reporter]] |

Ver [[Validación humana]] para lo que queda en manos de personas.
