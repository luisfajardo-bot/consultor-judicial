# Reglas de negocio

Tomadas del campo 6 de la spec inicial, con cómo quedó cada una implementada.

| Regla | Qué dice | Cómo está | Módulo |
|---|---|---|---|
| R1 | Una actuación nueva es POSIBLE NOVEDAD | Por `idRegActuacion` desconocido. Se reportan todas las nuevas, no solo la última | [[comparator]] |
| R2 | Primera consulta de un radicado: referencia, sin alerta | Se guarda todo y sale SIN CAMBIO "referencia inicial" | [[comparator]] |
| R3 | Sin resultados: NO VERIFICADO con motivo, nunca se elimina | También los radicados inválidos y los de forma inesperada | [[fetcher]] |
| R4 | Captcha, bloqueo o error: reintentos espaciados, luego NO VERIFICADO | 3 reintentos con espera creciente. Un 403 o 429 tiene su propia espera larga y pausa el ciclo | [[fetcher]] |
| R5 | Si falla más del X % del ciclo, se detiene y avisa "fuente no disponible" | 50 %, a partir de 10 consultas y otra vez al cerrar. Se cuentan las caídas, los sin resultados y las respuestas inesperadas, no los radicados inválidos | [[main]] |
| R6 | Una actuación alerta una sola vez; las Descartadas no se repiten | `alerta.id_reg_actuacion` es único | [[store]] |
| R7 | Se consulta por radicado, nunca por nombre | Un radicado que no tiene 23 dígitos no se consulta | [[loader]], [[fetcher]] |
| R8 | Cada ciclo deja bitácora; nada se borra | Tablas `ciclo` y `consulta`. El archivado de reportes no borra | [[store]] |
| R9 | Nunca escribe en el cuadro oficial ni envía nada fuera del equipo jurídico | El Excel se abre solo en lectura. La ventana no envía datos | [[loader]], [[reporter]] |

Ver [[Validación humana]] para lo que queda en manos de personas.
