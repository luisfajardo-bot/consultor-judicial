# reporter

**Qué hace:** genera el Excel de cada ciclo, lee de vuelta las decisiones de Alisson y escribe los avisos.

## El reporte
Archivo `reporte_ciclo_NNNN_AAAA-MM-DD.xlsx` en `reportes\`, con tres hojas:
- **Resumen:** totales, estado del ciclo, pendientes por consultar si el ciclo se pausó, y la leyenda obligatoria: "Alerta automática. No constituye notificación procesal ni actuación confirmada; verificar en la fuente oficial."
- **Alertas:** posibles novedades arriba, luego los NO VERIFICADO con su motivo, y las alertas pendientes de ciclos anteriores. Una fila por actuación nueva, con ID de alerta.
- **Sin cambio:** el resto, para que 500 filas sigan siendo legibles.

La columna **Decisión** trae un desplegable: Pendiente, Confirmada, Descartada. Ver [[Validación humana]].

## Seguridad y privacidad
- Un texto que empieza por `=` se guarda como texto, no como fórmula.
- Los caracteres de control (por ejemplo pegados desde Word) se eliminan en vez de romper el archivo.
- No muestra nombres de partes.

## Lectura de decisiones
`leer_decisiones` recorre los `reporte_*.xlsx` de la carpeta. Un archivo ilegible (abierto en Excel, dañado) se avisa y se reintenta en el siguiente ciclo. Una fila con ID de alerta inválido se ignora sin descartar el resto del archivo. Los reportes archivados ([[mantenimiento]]) no se leen.

## Aviso
`avisar` escribe en `reportes\avisos.log` con fecha y hora. Es el único punto de aviso: el canal real (correo o Teams) lo define Sistemas ([[Fase de escalamiento]]).

**Depende de:** openpyxl y [[store]]. Usado por [[main]].
