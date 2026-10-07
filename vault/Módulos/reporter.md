# reporter

**Qué hace:** genera el reporte consolidado del ciclo y envía el aviso.

**Salida:** Excel o CSV en el repositorio corporativo, con una fila por radicado: empresa, radicado, despacho, estado de la consulta, resultado, actuación anterior, actuación detectada, fecha y hora, fuente, enlace al proceso, estado de validación y quién validó.

**Orden:** arriba las POSIBLES NOVEDADES y los NO VERIFICADOS. Los SIN CAMBIO van en una hoja aparte, para que 500 filas sigan siendo legibles.

**Cabecera:** total consultados, exitosos, fallidos y posibles novedades.

**Columna "Decisión":** desplegable con Pendiente, Confirmada, Descartada. Ver [[Validación humana]].

**Leyenda obligatoria:** "Alerta automática. No constituye notificación procesal ni actuación confirmada; verificar en la fuente oficial."

**Privacidad:** no muestra nombres de partes que sean personas naturales.

**Aviso:** a Alisson Rengifo, con copia a Juan Uribe. Canal pendiente con Sistemas ([[Riesgos y pendientes]]).

**Depende de:** openpyxl y [[store]]. Usado por [[main]].
