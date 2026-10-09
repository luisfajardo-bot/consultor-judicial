# Operación y límites del portal

Todo lo de esta nota se midió contra el portal real el 2026-10-08 con 41 radicados activos.

## El portal limita las peticiones

- Corta con **HTTP 403** después de unas **60 a 70 peticiones**, vayan rápido o despacio. Es una cuota, no una velocidad.
- El bloqueo dura **más de 90 s y menos de unos 2,5 minutos**. Después responde 200 otra vez.
- Un radicado cuesta 2 a 4 peticiones: búsqueda, una o dos páginas de actuaciones y, si está activado, el detalle.
- Un ciclo de 41 radicados choca con la cuota una o dos veces.

## Cómo lo maneja [[fetcher]]

1. Pausa de 1,5 s entre peticiones (`pausa_peticiones_segundos`).
2. El detalle (fecha de replicación) viene apagado (`consultar_detalle = false`) para ahorrar una petición por radicado.
3. Ante un 403 o 429 espera 60, 120 y 240 s y reintenta (`reintentos_bloqueo`, `espera_bloqueo_segundos`). Casi siempre se recupera solo.
4. Si aun así sigue bloqueado, [[main]] **pausa el ciclo**: no registra el radicado bloqueado ni los siguientes, escribe el reporte con lo ya consultado, avisa cuántos quedan y sale con código 1.
5. La siguiente ejecución del mismo día **continúa desde ahí** sin repetir lo hecho. El límite entre ejecuciones sirve de enfriamiento.

Resultado real: ciclo de 41 radicados en 1 a 8 minutos según cuánto frene el portal.

## Candado, límite entre ejecuciones y avance

- [[main]] toma un candado del sistema operativo: dos ciclos a la vez son imposibles. Si el proceso muere, se libera solo.
- Si la última consulta terminó hace menos de `min_minutos_entre_ciclos` (30 por defecto), se niega y dice a qué hora se puede. `--forzar` lo salta, el candado no.
- Una consulta de un solo radicado (`--solo-radicado`) no cuenta para ese límite.
- Con consola, se ve una barra de avance. El avance también se publica en `estado.txt` para quien intente lanzar un segundo ciclo.
- `scripts\ejecutar_ahora.bat` es el doble clic para personas no técnicas.

## Cancelar un ciclo

- El botón **Cancelar** de la [[panel y ventana]] pide la cancelación creando `cancelar.txt` en la carpeta de datos. El ciclo lo detecta entre radicados y durante las esperas largas, termina el radicado en vuelo sin registrarlo y queda **"Cancelado por el usuario"**.
- Lo ya consultado se conserva. El ciclo se reanuda el mismo día, sin esperar el límite de 30 minutos entre ejecuciones.
- Sirve también para el ciclo programado, aunque corra oculto.
- Ctrl+C en una consola también cancela de forma segura. **Cerrar la ventana negra corta el programa a la fuerza** (código `0xC000013A`): no se pierde nada ya guardado, pero queda un `estado.txt` viejo. La ventana ya lo ignora.

## Ejecución oculta

La tarea programada lanza `pythonw.exe` (sin ventana de consola), así nadie puede cortarla cerrando una ventana. Sin consola, la salida y los errores van a `reportes\consola.log` y los avisos a `reportes\avisos.log`. Para ver el avance se abre la ventana.

## Mantenimiento al final de cada ciclo

- **Archivado:** los reportes con más de 14 días pasan a `reportes\archivo\AAAA-MM\`. No se borran. Nunca se archiva el reporte más reciente. Un archivo abierto en Excel se salta y se reintenta en el siguiente ciclo.
- **Borrado del archivo:** existe pero está apagado (`borrar_archivo_tras_dias = 0`). El plazo de conservación como evidencia lo decide la Gerencia Jurídica.
- **Respaldo de la base:** cada 7 días, con la función de respaldo de SQLite, verificado con `integrity_check`, en `datos\respaldo\`. Se conservan las últimas 8 copias.
- Un fallo del mantenimiento nunca tumba el ciclo ni cambia el código de salida: se avisa y se sigue.
- Decidir en un reporte archivado no se importa. Las alertas pendientes reaparecen siempre en el reporte más reciente, y ahí se decide.
- Los reportes pesan unos 10 KB, así que el motivo de archivar es el orden, no el disco.

## Alertas que puede dar la herramienta

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| ALERTA: el portal bloqueó las consultas | Cuota del portal agotada | Esperar el tiempo indicado y volver a lanzar |
| ALERTA: la API posiblemente cambió | Respuestas con forma inesperada | Volver a la consulta manual y avisar a quien mantiene la herramienta |
| Fuente no disponible | Fallan demasiadas consultas | Consulta manual, ver [[Validación humana]] |
| Lista vacía | La fuente no devolvió radicados | Revisar el Excel y el filtro de estado |

## Base de datos

Todas las consultas por radicado usan índice. Con 500 radicados × 40 actuaciones y 40 ciclos, la base ocupa unos 8 MB y le toma de 3 a 7 s por ciclo, menos del 1 % del tiempo total.

No se usa el modo WAL de SQLite: no es seguro si la carpeta de datos queda en una unidad de red.

## Datos de la lista real

La hoja `GENERAL` trae `RADICADO` (23 dígitos), `ESTADO` y `DESPACHO`, pero no una columna de empresa. 77 filas con datos, 68 radicados válidos (65 únicos) y 8 con formato inválido, que quedan como NO VERIFICADO con el motivo hasta que Alisson los depure. El filtro de estado acepta variantes: `ACTIVO` incluye `ACTIVO -COBRO COSTAS`.

Ver [[API Rama Judicial]] y [[Riesgos y pendientes]].
