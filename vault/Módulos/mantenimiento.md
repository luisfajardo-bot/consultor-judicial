# mantenimiento

**Qué hace:** ordena los reportes y respalda la base de datos. Corre **al final de cada ciclo** que se ejecutó, dentro de [[main]]. Un fallo ahí se avisa y nunca cambia el código de salida.

## Archivado de reportes
- Los reportes con más de 14 días pasan a `reportes\archivo\AAAA-MM\`. No se borran.
- Nunca se archiva el reporte más reciente.
- Un archivo abierto en Excel se salta y se reintenta en el siguiente ciclo.
- Se ignoran los nombres que no cuadran con `reporte_ciclo_NNNN_AAAA-MM-DD.xlsx` y los temporales `~$`.
- Decidir en un reporte archivado no se importa. Las alertas pendientes reaparecen siempre en el reporte más reciente, y ahí se decide.

## Borrado del archivo
Existe pero está **apagado** (`borrar_archivo_tras_dias = 0`). El plazo de conservación como evidencia lo decide la Gerencia Jurídica.

## Respaldo de la base
- Cada 7 días, con la función de respaldo de SQLite, que es segura aunque la base esté en uso.
- Se escribe a un archivo `.tmp`, se verifica con `integrity_check` y solo entonces recibe su nombre definitivo `consultor_AAAA-MM-DD.db`. Un respaldo que no pasa la verificación se descarta.
- Se guardan en `datos\respaldo\` y se conservan las últimas 8.
- **Por defecto están en el mismo equipo que la base**, así que no protegen de un fallo de disco. `carpeta_respaldo` en `config.toml` permite apuntar a una carpeta de red.

Los reportes pesan unos 10 KB: el motivo de archivar es el orden, no el espacio. Ver [[Operación y límites del portal]] y [[store]].
