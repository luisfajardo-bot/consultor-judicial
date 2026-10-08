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
- Botón **Consultar ahora**: corre `ejecutar_ciclo` en un hilo aparte. Se desactiva mientras corre otro ciclo, sea de la ventana o de la tarea programada.
- Botón **Abrir último reporte**.

## Cuidados
- No envía datos a ningún servicio externo.
- No abre la base mientras hay un ciclo en curso, para no esperar un bloqueo de SQLite.
- Solo Windows. En Linux y Docker no hay ventana.
- Las pruebas usan una sola raíz de tkinter por sesión: crear y destruir varias en el mismo proceso falla de forma intermitente en Windows.

Se abre con `scripts\abrir_panel.bat` o `python -m consultor ventana`. Ver [[bloqueo]] y [[main]].
