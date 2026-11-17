# panel y ventana

**Qué hace:** una pantalla mínima para ver que la consulta está en marcha y lanzarla a mano.

## Dos capas
- **`panel.py` (lógica, sin tkinter):** lee el avance de `estado.txt`, resume el último ciclo, encuentra el último reporte y arma los textos. Se prueba sin abrir ninguna ventana.
- **`ventana.py` (vista, tkinter):** solo dibuja. No decide nada.

Esa separación es la **arquitectura para escalar**: otra vista (por ejemplo una web) reutiliza `panel.py` y `ejecutar_ciclo` sin tocarlos. Ampliar la pantalla es una decisión de otra gerencia ([[Fase de escalamiento]]).

## Qué muestra
- Barra de progreso con "12 de 44" y la hora de inicio.
- "Sin avance hace N min: el portal puede estar pidiendo esperar", si pasan más de 90 s sin avance. Casi siempre es la espera por el bloqueo del portal y no hay que hacer nada.
- Resumen de la última consulta: consultados, exitosos, sin verificar, posibles novedades y alertas por validar.
- Botón **Consultar ahora**: corre `ejecutar_ciclo` en un hilo aparte. Se desactiva mientras corre otro ciclo, sea de la ventana o de otro equipo.
- Botón **Abrir último reporte**.
- **Alertas por decidir** (ver abajo), el campo de días y el aviso al cerrar.

## Decidir alertas en la ventana
- Dos pestañas: **Por decidir · últimos N días** y **Anteriores sin decidir**. N es el campo de días (el mismo que usa la primera consulta de un radicado). La fecha de detección es la de la consulta que creó la alerta, no la de la actuación.
- Tabla con casillas, **Seleccionar todas**, **Confirmar seleccionadas** y **Descartar seleccionadas** (pregunta si son más de 5), detalle de la fila y **Abrir en el portal** (copia el radicado).
- **Ver decididas**: filtro, corrección a Confirmada, Descartada o Pendiente, e historial por alerta. Todo pasa por `Store.decidir`, que cambia `alerta` e inserta en `decision` en una sola transacción.
- La lista no se recarga en cada vuelta de `sondear()`: solo al abrir, tras decidir, al terminar una consulta, al guardar días o cuando cambia el último ciclo. Se conservan las casillas marcadas.
- Con la base ocupada por una consulta, la ventana avisa y reintenta; no se cuelga.
- `panel.py` tiene la lógica (`separar`, `contar_para_regla`, `evaluar_obligacion`, `accion_al_cerrar`, textos); `ventana.py` solo pinta.

## Al cerrar y regla de puesta al día
- `WM_DELETE_WINDOW` pasa por `Ventana.al_cerrar`: 1) obligación activa: aviso sin opción de cerrar ("bloqueada"); 2) pendientes en el rango: pregunta si cierra igual ("cancelada" o "cerrada"); 3) nada pendiente: cierra. Una consulta en curso no cambia los pasos. Si la base falla al cerrar, usa lo último leído; si nunca se pudo leer, pregunta si cierra igual (la ventana nunca queda trabada).
- La regla (R10 en [[Reglas de negocio]]) está **apagada** por defecto: se enciende en `[alertas]` de `config.toml`. Activa, muestra un aviso rojo de una línea sobre las pestañas y abre en Anteriores. **Consultar ahora** no se bloquea.
- Usa su propio corte (`dias_corte_regla`), no el campo de días de la ventana. La obligación se guarda en `estado_app` ([[store]]); si la base está ocupada al guardarla, la ventana conserva el último estado conocido.

## Estado confiable y cancelación
- El avance solo se muestra si el candado está realmente tomado ([[bloqueo]]). Un archivo viejo no hace creer que hay una consulta corriendo ni desactiva **Consultar ahora**.
- **Cancelar consulta** se habilita solo mientras corre un ciclo, pide confirmación y crea `cancelar.txt`. Funciona con cualquier ciclo. Lo ya consultado se conserva.

## Cuidados
- No envía datos a ningún servicio externo.
- Mientras hay un ciclo en curso no lee el resumen de la base, pero la lista de alertas sí se lee y se decide: al decidir prueba la base con espera corta (2 s) y, si está ocupada, avisa sin perder la selección; si una lectura la encuentra ocupada, conserva lo último leído y reintenta en la siguiente vuelta.
- Solo Windows. En Linux y Docker no hay ventana.
- Las pruebas usan una sola raíz de tkinter por sesión: crear y destruir varias en el mismo proceso falla de forma intermitente en Windows.

Se abre con `scripts\abrir_panel.bat` o `python -m consultor ventana`. Ver [[bloqueo]] y [[main]].
