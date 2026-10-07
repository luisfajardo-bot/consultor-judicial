# store

**Qué hace:** guarda el histórico, la bitácora y el estado de validación en SQLite.

## Tablas

- `radicado`: radicado, empresa, despacho, `id_proceso`, activo
- `actuacion`: `id_reg_actuacion` (clave), radicado, `fecha_actuacion`, actuación, anotación, `fecha_registro`, `fecha_inicial`, `fecha_final`, `primera_vez_visto`
- `alerta`: radicado, `id_reg_actuacion`, ciclo, estado (Pendiente, Confirmada, Descartada), validada_por, validada_en
- `ciclo`: inicio, fin, totales, estado final
- `consulta`: ciclo, radicado, hora, resultado, motivo del fallo, fecha de replicación

Cada consulta se registra al terminar. Si el ciclo se interrumpe, el siguiente arranque continúa donde quedó.

Nada se borra (R8).

## Única puerta de escritura de decisiones

`registrar_decision(alerta_id, estado, usuario)`. La llama el lector del Excel hoy y podría llamarla una web mañana. Ver [[Validación humana]].

Usado por [[main]] y [[reporter]]. Reglas R6 y R8 en [[Reglas de negocio]].
