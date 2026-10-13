# store

**Qué hace:** guarda el histórico, la bitácora y el estado de validación en SQLite (`datos\consultor.db`).

## Tablas
- `radicado`: radicado, empresa, despacho, `id_proceso`
- `actuacion`: `id_reg_actuacion` (clave), radicado, fecha, actuación, anotación, fechas de término, primera vez vista
- `ciclo`: inicio, fin, estado, `parcial`. Estados: En curso, Completo, Completo con fallas de la fuente, Completo con alerta de API, Detenido, Pausado, Interrumpido
- `consulta`: una por radicado y ciclo, con hora, resultado, motivo
- `alerta`: radicado, actuación, ciclo, estado (Pendiente, Confirmada, Descartada), quién validó y cuándo. `id_reg_actuacion` es único, así que una actuación alerta una sola vez (R6)

Nada se borra (R8).

## Índices
Todas las consultas por radicado usan índice (`ix_consulta_radicado`, `ix_alerta_ciclo` y el parcial `ix_alerta_pendiente`; `ix_actuacion_radicado_fecha` se conserva en el esquema pero `ultima_actuacion` ya no lo usa). Una base con 500 radicados y 40 ciclos pesa unos 8 MB. Las bases ya creadas se migran al abrirlas.

No se usa el modo WAL: no es seguro si la carpeta queda en una unidad de red.

## Operaciones clave
- `registrar_resultado`: guarda actuaciones, consulta y alertas **en una sola transacción**. Si el proceso se cae, no queda una actuación conocida sin su alerta.
- `iniciar_ciclo`: continúa el ciclo En curso o Pausado del mismo día (reanudación). Los de días anteriores se marcan Interrumpido.
- `registrar_decision(alerta_id, estado, usuario)`: **única puerta de escritura** de decisiones. Solo cambia alertas Pendiente, así que la primera decisión es la que cuenta. Una página web futura sería otro cliente de esta función.
- `filas_reporte`: arma el reporte de un ciclo e incluye las alertas Pendiente de ciclos anteriores.
- `ultimo_cierre`, `ultimo_ciclo`, `contar_pendientes`: usadas por el límite entre ejecuciones y el [[panel y ventana]].

Reglas R6 y R8 en [[Reglas de negocio]]. Usado por [[main]] y [[reporter]]. Respaldos en [[mantenimiento]].

## Cambios tras la auditoría (2026-10-13)
- Tabla nueva `actuacion_radicado(radicado, id_reg_actuacion)`: lo que cada radicado recibió en una consulta exitosa. Se llena una vez desde `actuacion` cuando la tabla se crea por primera vez.
- `ids_vistos(radicado, ids)` devuelve lo que ese radicado ya conoce más los ids que ya tienen alerta (una actuación alerta una sola vez en todo el sistema, R6). Motivo: dos radicados pueden devolver el mismo proceso. Un "visto" global ocultaba una novedad real, y una clave por `actuacion` hacía que el segundo radicado alertara de más y desapareciera del reporte.
- `filas_reporte` siempre da una fila por radicado consultado. Una novedad sin alerta muestra "novedad sin alerta registrada".
- `ultimo_cierre` ignora los ciclos Interrumpido y Cancelado. `ultima_actuacion` lee a través de la tabla de enlace.
