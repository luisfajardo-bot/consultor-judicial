# Consultor Judicial

Consulta los radicados de la lista en la API de la Rama Judicial, detecta actuaciones nuevas y deja un Excel de alertas para que Alisson Rengifo las valide. No decide nada jurídico y no escribe en el cuadro oficial.

## Requisitos

- **Python 3.11 o superior** (probado en 3.12 y 3.14, en Windows y en Linux).
- Dependencias: `requests` y `openpyxl`, fijadas en `requirements.txt`. Para desarrollar y probar, `requirements-dev.txt` añade `pytest`.
- La ventana usa `tkinter`, que viene con Python en Windows y no se instala con pip. En Linux y en Docker no hay ventana: el programa funciona igual desde la línea de comandos.

## Instalación

Windows:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy config.example.toml config.toml
```

Linux o macOS:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp config.example.toml config.toml
```

Edita `config.toml`: ruta del Excel con los radicados y nombres de sus columnas. `config.toml` no se sube a git.

## Uso

```
python -m consultor run
python -m consultor run --solo-radicado 11001400307720210114700
python -m consultor run --forzar
python -m consultor ventana
```

`--forzar` salta el límite entre ejecuciones (no el candado). `ventana` abre la pantalla (solo Windows).

Códigos de salida: 0 ciclo completo, 1 pausado, detenido o con alertas (portal bloqueado, API cambiada, fuente no disponible), 2 error inesperado, 3 no se ejecutó porque ya hay otro ciclo en curso o la última consulta es muy reciente.

## Datos que no deben subirse a git

El Excel de procesos, `config.toml`, `datos\` (la base SQLite) y `reportes\` contienen la posición litigiosa de la empresa. `.gitignore` ya los excluye; no los fuerces.

## Pruebas

```
pip install -r requirements-dev.txt
python -m pytest
```

En Linux sin librerías gráficas, las pruebas de la ventana se saltan solas.

## Validación

Se puede decidir de dos maneras: desde la ventana (ver "Pantalla") o en el Excel.

En el Excel: abrir `reportes\reporte_ciclo_NNNN_AAAA-MM-DD.xlsx`, hoja Alertas. En cada fila con ID de alerta elegir en la columna Decisión: Confirmada o Descartada (y escribir el nombre en Validó). Guardar y cerrar el archivo. El ciclo siguiente lee la decisión. Una decisión del Excel solo vale si la alerta sigue Pendiente y el reporte es posterior a su último cambio: un reporte viejo no pisa lo que se corrigió después en la ventana, y el programa avisa cuántas decisiones ignoró por eso.

## Ejecutar a mano

Doble clic en `scripts\ejecutar_ahora.bat`. Se ve una barra de avance con el radicado que se está consultando; no cierres la ventana. Al terminar, el reporte se abre en Excel.

- Si ya hay una consulta en curso (por ejemplo, otra persona desde su equipo), el programa lo dice, muestra su avance y no hace nada: el candado impide dos ciclos a la vez.
- Si la última consulta terminó hace menos de 30 minutos, el programa lo dice y no hace nada, para no repetir consultas al portal. El límite se cambia en `config.toml`, sección `[ejecucion]`, con `min_minutos_entre_ciclos` (0 lo desactiva). Quien administra la herramienta puede saltarlo con `--forzar`.
- Código de salida 3: no se ejecutó por candado o por el límite. Los demás: 0 completo, 1 detenido o con fallas, 2 error inesperado.

## Pantalla

Doble clic en `scripts\abrir_panel.bat`. Se abre una ventana que muestra:

- Una barra de progreso con el radicado hecho de total, mientras hay una consulta en curso.
- El resumen de la última consulta: cuántos radicados se consultaron, cuántos posibles novedades hay y cuántas alertas faltan por validar.
- El botón **Consultar ahora**, que lanza una consulta con las mismas reglas de siempre.
- El botón **Abrir último reporte**, que abre el Excel más reciente.
- El botón **Cancelar**, activo solo mientras hay una consulta en curso. Pide confirmación y detiene la consulta al terminar el radicado actual. Lo ya consultado se conserva y se puede continuar más tarde: la siguiente consulta del mismo día sigue desde donde quedó, sin esperar el límite entre ejecuciones.
- El botón **Apagar consultas / Encender consultas**: interruptor de este equipo. Apagado, **Consultar ahora** (ni `--forzar`) no sale a la Rama Judicial. Sirve cuando varias personas consultan desde la misma red: el portal cuenta todo lo que sale de una misma IP, así que conviene que solo un equipo consulte a la vez. No detiene una consulta que ya esté en curso (para eso, **Cancelar**). Queda en `datosjustes.json`; si ese archivo falta, las consultas están encendidas.

- Un campo **días** que hace dos cosas: (1) en un radicado que se consulta por primera vez, lo registrado en esos últimos días sale como POSIBLE NOVEDAD, y lo más antiguo queda como referencia; rige desde la siguiente consulta; (2) define qué alertas van en la pestaña **Por decidir** (ver abajo), y eso rige de inmediato. Por defecto 7; 0 no avisa nada en radicados nuevos y deja en Por decidir solo lo detectado hoy. Se guarda al salir del campo o con Enter y queda en `datos\ajustes.json`. Si ese archivo existe, manda sobre `[primera_consulta]` de `config.toml`.

### Decidir las alertas desde la ventana

Debajo del campo de días hay dos pestañas: **Por decidir · últimos N días (n)**, con las alertas pendientes detectadas en esos días, y **Anteriores sin decidir (n)**, con las pendientes detectadas antes. La fecha de detección es la de la consulta que la creó, no la de la actuación. Si no queda nada, la lista dice "Al día ✓".

1. Marcar las casillas de las alertas (clic en la casilla o barra espaciadora), o usar **Seleccionar todas**.
2. Al elegir una fila se ve su detalle (radicado, despacho, actuación, anotación). **Abrir en el portal** abre la consulta de la Rama Judicial y copia el radicado para pegarlo ("Radicado copiado").
3. **Confirmar seleccionadas** (la actuación es real y ya se revisó en el portal) o **Descartar seleccionadas** (no requiere acción: repetida, trámite sin efecto, error). Con más de 5 alertas pide confirmación.

La decisión queda con el nombre de `validador` en `[salida]` de `config.toml`.

**Ver decididas** abre la lista de alertas ya decididas, con filtro por Confirmada o Descartada. Se pueden corregir: seleccionar una o varias y pasarlas a Confirmada, Descartada o Pendiente (vuelve a la lista de pendientes). Al elegir una fila se ve su historial: quién, cuándo, de qué estado a cuál y por qué vía (ventana, Excel o migración). Nada se borra.

**Al cerrar la ventana**, si quedan alertas en Por decidir, pregunta "Quedan n alertas por decidir de los últimos N días. ¿Cerrar de todas formas?". Con una consulta en curso rige lo mismo.

### Regla de puesta al día (apagada)

Sistemas la enciende en `config.toml`, sección `[alertas]`, con `exigir_puesta_al_dia = true`, cuando la Gerencia Jurídica lo indique. Hasta entonces no hace nada. Encendida: si las alertas pendientes detectadas hace más de `dias_corte_regla` días (7 por defecto) pasan de `umbral_anteriores` (30), la ventana muestra un aviso rojo, abre en la pestaña Anteriores y no se cierra hasta dejarlas en menos de `objetivo_anteriores` (10). La regla usa su propio corte, no el campo de días, así que no se esquiva cambiándolo. La obligación queda guardada en la base: si se cierra a la fuerza, al volver a abrir sigue. **Consultar ahora** nunca se bloquea.

Si ya hay otra consulta corriendo (por ejemplo, otra persona desde su equipo), el botón **Consultar ahora** queda desactivado y la barra muestra su avance. Cuando aparece "Sin avance hace N min", casi siempre es el portal pidiendo esperar: no hay que hacer nada, la consulta sigue sola. La ventana no envía datos a ningún sitio: trabaja con los archivos de esta carpeta y guarda en la base las decisiones que se toman en ella. **Abrir en el portal** solo abre la página de consulta de la Rama Judicial en el navegador y copia el radicado; no manda nada.

Si la consulta corre en una consola, Ctrl+C también la cancela de forma segura. Cerrar la ventana negra, en cambio, corta el programa a la fuerza: el ciclo queda interrumpido y se reanuda en la siguiente consulta, pero conviene usar **Cancelar**.

## Reportes antiguos y copias de seguridad

Al terminar cada consulta la herramienta hace dos tareas de orden, sin que nadie tenga que hacer nada.

**Reportes antiguos.** Los reportes con más de 14 días se mueven (no se borran) a `reportes\archivo\AAAA-MM\`. El reporte para validar es siempre el más reciente, que nunca se archiva: las alertas pendientes reaparecen ahí en cada consulta nueva. Marcar una decisión en un reporte archivado no se importa, así que hay que decidir en el más reciente. Si un reporte está abierto en Excel no se mueve y se reintenta en la siguiente consulta.

**Copias de seguridad de la base de datos.** Cada 7 días se guarda una copia en `datos\respaldo\` (archivos `consultor_AAAA-MM-DD.db`) y se conservan las 8 más recientes. Cada copia se verifica al crearla.

**Cómo restaurar una copia.** Cerrar todo (la ventana y cualquier consulta en curso), elegir el respaldo que se quiere y copiarlo sobre `datos\consultor.db`.

**Borrado de archivados.** La opción de borrar reportes archivados existe, pero está apagada (`borrar_archivo_tras_dias = 0` en `config.toml`, sección `[mantenimiento]`). Se activará cuando la Gerencia Jurídica decida el plazo de conservación.

Si algo falla en estas tareas, la consulta no se afecta: queda un aviso en `reportes\avisos.log`.

## Si la API cambia

La Rama Judicial no documenta su API y puede cambiarla sin aviso. Si pasa, la herramienta muestra el mensaje "ALERTA: la API de la Rama Judicial posiblemente cambió" y el ciclo termina como "Completo con alerta" o "Detenido: posible cambio en la API".
En el reporte, los radicados afectados aparecen como NO VERIFICADO, con el motivo "respuesta inesperada".
Mientras tanto, vuelva a la consulta manual en el portal de la Rama Judicial y no confíe en los resultados de ese ciclo.
Avise a quien mantiene la herramienta para que la ajuste.

## Si el portal bloquea las consultas

Si el portal de la Rama Judicial recibe muchas consultas seguidas, puede bloquearlas por un rato. En ese caso la herramienta se detiene de inmediato y muestra el mensaje "ALERTA: el portal bloqueó las consultas".
El reporte de Excel trae lo consultado hasta ese momento, y en la hoja Resumen aparece cuántos radicados quedaron pendientes ("Pendientes por consultar"). El ciclo queda como "Pausado: el portal bloqueó las consultas".
No hace falta hacer nada más que esperar el tiempo que indica el mensaje (30 minutos por defecto) y volver a lanzar la herramienta. Continuará sola desde donde quedó, sin repetir lo ya consultado.

## Limitaciones conocidas

- Las decisiones se pueden corregir desde la ventana (**Ver decididas**), con historial. En el Excel solo cuenta la decisión de una alerta Pendiente, y un reporte viejo no pisa lo corregido después en la ventana.
- Un cierre forzado de la ventana (Administrador de tareas, apagar el equipo) no se puede impedir, aunque la regla de puesta al día esté encendida.
