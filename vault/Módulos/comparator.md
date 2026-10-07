# comparator

**Qué hace:** recibe las actuaciones traídas y las guardadas de un radicado, y devuelve su clasificación.

| Entrada | Resultado |
|---|---|
| Radicado visto por primera vez | Guarda como referencia, sin alerta (R2) |
| Actuaciones con `idRegActuacion` no guardado | POSIBLE NOVEDAD, con todas las nuevas (R1) |
| Ninguna actuación nueva | SIN CAMBIO |
| Sin resultados o error tras reintentos | NO VERIFICADO con motivo (R3, R4) |

Una actuación ya alertada o Descartada no vuelve a alertar (R6).

**Lógica pura:** sin red ni disco, así que se prueba con casos escritos a mano.

**Depende de:** nada. Reglas en [[Reglas de negocio]]. Usado por [[main]].
