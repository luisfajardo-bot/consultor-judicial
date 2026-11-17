# Decidir alertas desde la ventana: documento de diseño

Fecha: 2026-11-17
Estado: borrador para revisión
Origen: auditoría del 2026-11-17 sobre "alertas con más días de los configurados"

## 1. Por qué

La base real (copia del 2026-11-17) tiene 51 alertas y ninguna decidida. Cada reporte vuelve a listar todas las pendientes, así que el del 13-nov mostraba 51 filas con fechas desde el 09-oct mientras su Resumen decía 5 novedades. Eso es lo que se percibía como "alertas con más días de los configurados".

Alisson no ha decidido porque marcar fila por fila en el Excel es tedioso y el proceso no estaba claro. Se quiere que decidir sea rápido (varias o todas de una vez), que lo viejo no quede olvidado y que quede trazabilidad de quién decidió qué y cuándo, incluidas las correcciones.

La herramienta corre siempre desde el equipo de Alisson; las bases por equipo no son un problema para este cambio.

## 2. Objetivos, no objetivos y anti-objetivos

Objetivos:

- Ver en la ventana principal las alertas pendientes, separadas en "las del rango de días" y "las anteriores".
- Confirmar o descartar varias alertas de una vez.
- Corregir una decisión ya tomada, con historial completo y sin borrar nada.
- Avisar al cerrar si quedan pendientes en el rango.
- Dejar construida, y apagada, una regla que obligue a ponerse al día cuando las anteriores pasan de 30.

No objetivos:

- Cambiar cómo se detectan las alertas ni qué hace el campo "días" en la primera consulta de un radicado.
- Corregir los otros hallazgos de la auditoría (fecha de registro fuera del reporte, día de más en la ventana, bases por equipo). Van aparte.
- Notificaciones por correo o Teams.
- Quitar la decisión desde el Excel: sigue funcionando.

Anti-objetivos (aunque funcione, sería un fracaso si):

- Una decisión tomada en la ventana se pierde o un Excel viejo la pisa en silencio.
- Con la regla apagada, la ventana no se deja cerrar.
- Se frena el monitoreo: "Consultar ahora" nunca se bloquea por alertas sin decidir.
- La lista se reinicia mientras Alisson está seleccionando (por el refresco de cada segundo).

## 3. Enfoques considerados

| Enfoque | Qué implica | Por qué sí o no |
|---|---|---|
| **Ampliar la ventana tkinter actual + historial en SQLite** | Lista con pestañas en `ventana.py`, lógica en `panel.py`, tabla nueva en `store.py` | **Elegido.** Es lo que Alisson ya usa, no suma dependencias y respeta R9 |
| Página web local | Servidor local y navegador | Otra pieza que mantener y otro programa que abrir; choca con "la ventana no expone nada" |
| Mejorar solo el Excel | Más columnas o una macro | Elegido decidir en la ventana; el Excel no puede impedir cerrar ni mostrar contadores |

Dentro de la ventana se mostraron dos acomodos: A, la lista en la ventana principal con pestañas, y B, un botón que abre una ventana aparte. Luis eligió **A**.

## 4. Lo que decidió Luis

- La lista va en la ventana principal, debajo de los botones y del campo de días, con dos pestañas: **"Por decidir · últimos N días (n)"** y **"Anteriores sin decidir (n)"**.
- N es el mismo campo "días" que ya existe en la ventana.
- Se seleccionan varias (casillas y "Seleccionar todas") y se aplica **Confirmar seleccionadas** o **Descartar seleccionadas**.
- Al cerrar con pendientes en el rango: aviso "Quedan n alertas por decidir de los últimos N días. ¿Cerrar de todas formas?" con **Volver a revisar** y **Cerrar igual**.
- Las decisiones **se pueden corregir**, con historial.
- **Regla de puesta al día**: cuando las anteriores sin decidir pasan de 30, hay que dejarlas en menos de 10 en una sola sentada. Mientras tanto la ventana no se cierra de forma normal y muestra un aviso rojo al abrirla. "Consultar ahora" no se bloquea. **Se construye apagada**; se enciende cuando Luis lo indique, porque hoy el atraso lo tendría que resolver él y no es el responsable.
- Todo se sube desde la cuenta de GitHub **luisfajardo-bot**.

## 5. Diseño

### 5.1 Qué alerta va en cada pestaña

- **Fecha de detección** de una alerta: la fecha de la consulta del ciclo y radicado donde se creó (`consulta.hora` con `consulta.ciclo_id = alerta.ciclo_id` y `consulta.radicado = alerta.radicado`; si falta, `ciclo.inicio`). No se usa la fecha de la actuación: la alerta 50 de la base real es una actuación del 22-oct que el portal mostró recién el 13-nov, y por fecha de actuación nunca habría entrado al rango.
- **Rango**: detectada en la fecha `hoy − N días` o después, con la misma convención que `_desde` en `main.py` (fechas de calendario, inclusive). Con N = 0, el rango es solo hoy.
- **Por decidir**: pendientes dentro del rango. **Anteriores sin decidir**: pendientes detectadas antes del rango.
- Ambas pestañas se ordenan de la más reciente a la más antigua por fecha de detección.

**El campo "días" hace ahora dos cosas** (decisión de Luis: la lista usa los días establecidos en el programa). Para que nadie cambie una sin saber que cambia la otra *(criterio del diseño)*:

- La etiqueta pasa a: "Días a revisar: avisar lo registrado en los últimos [N] días (también define la pestaña Por decidir)".
- Al guardar, el texto de confirmación dice las dos cosas: "Guardado: 7 días. La pestaña Por decidir ya muestra los últimos 7 días; en radicados nuevos rige desde la próxima consulta."
- Con 0: "Guardado: 0 días. No se avisará nada en radicados nuevos; Por decidir muestra solo lo detectado hoy."
- Guardar el campo recarga la lista de inmediato (ya figura en 5.3).

### 5.2 Pantalla

Debajo del campo de días, en este orden:

1. Pestañas con contador.
2. Texto de ayuda fijo: *Confirmar = la actuación es real y ya la revisé en el portal. Descartar = no requiere acción (repetida, trámite sin efecto, error).*
3. Botones: **Seleccionar todas** (alterna con "Quitar selección"), **Confirmar seleccionadas**, **Descartar seleccionadas**, **Ver decididas**.
4. Tabla: casilla, Detectada, Radicado, Fecha actuación, Actuación.
5. Detalle de la fila enfocada: radicado completo, despacho, actuación, anotación completa, ciclo en que se detectó, y botón **Abrir en el portal**.
6. Si una pestaña está vacía: "Al día ✓".

Boceto aprobado (opción A):

```
Consultor Judicial
Consultas de este equipo: ENCENDIDAS
Última consulta: 2026-11-13 14:55 (Completo) · 77 consultados
[Consultar ahora] [Abrir último reporte] [Cancelar] [Apagar consultas]
Avisar lo registrado en los últimos [7] días
───────────────────────────────────────────────
| Por decidir · últimos 7 días (7) | Anteriores sin decidir (44) |
Confirmar = ... ya la revisé en el portal. Descartar = no requiere acción.
[Seleccionar todas] [Confirmar seleccionadas] [Descartar seleccionadas] [Ver decididas]
☑ 13-nov  …0420200011000  10-nov  Envío de Comunicación
☑ 13-nov  …0420200011000  10-nov  Fijacion estado
☐ 13-nov  …0120190033800  11-nov  Agregar Memorial
Detalle: 17001333300420200011000 · JUZGADO 004 ... · Anotación: ...  [Abrir en el portal]
```

**Abrir en el portal** abre `ENLACE_PORTAL` (el portal no admite enlace directo por radicado) y copia el radicado al portapapeles, avisando "Radicado copiado".

Aplicar una decisión en bloque pide confirmación solo si son más de 5: "¿Descartar 12 alertas? Se puede corregir desde Ver decididas." Al aplicar, las filas salen de la lista y los contadores se actualizan.

**Ver decididas** abre una ventana secundaria con las alertas ya decididas: Decisión, Decidida en, Por, Radicado, Actuación. Se puede filtrar por Confirmada o Descartada y seleccionar una o varias para pasarlas a **Confirmada**, **Descartada** o **Pendiente**. Una fila muestra su historial (quién, cuándo, de qué a qué, origen).

### 5.3 Refresco sin perder la selección

`sondear()` corre cada segundo. La lista **no** se recarga en cada vuelta. Se recarga:

- al abrir la ventana;
- después de aplicar o corregir una decisión;
- cuando termina una consulta lanzada desde la ventana;
- cuando cambia el valor de días guardado;
- cuando cambia `ultimo_ciclo()` (otra consulta terminó). Se compara el id en cada vuelta, que es barato.

Al recargar se conservan las casillas marcadas de las alertas que siguen en la lista.

### 5.4 Datos

Tabla nueva, solo se agregan filas:

```sql
CREATE TABLE IF NOT EXISTS decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alerta_id INTEGER NOT NULL,
    estado_anterior TEXT NOT NULL,
    estado_nuevo TEXT NOT NULL,
    usuario TEXT NOT NULL,
    momento TEXT NOT NULL,
    origen TEXT NOT NULL);          -- 'ventana' | 'excel' | 'migracion'
CREATE INDEX IF NOT EXISTS ix_decision_alerta ON decision(alerta_id, id);
```

`alerta.estado`, `validada_por` y `validada_en` siguen guardando el estado vigente (el reporte y el panel ya los leen). Cada cambio actualiza `alerta` e inserta en `decision` **en la misma transacción**.

Migración, en `Store.__init__` y a prueba de cortes como la de `actuacion_radicado`: por cada alerta ya decidida sin filas en `decision`, insertar una con `estado_anterior = 'Pendiente'`, el estado actual, `validada_por`, `validada_en` y `origen = 'migracion'`. Hoy no hay ninguna en la base real, pero puede haberlas en otras copias.

Métodos de `Store`:

- `decidir(alerta_ids, estado, usuario, ahora, origen) -> int`: aplica a todas en una transacción. Acepta `Confirmada`, `Descartada` y `Pendiente`. Ignora las que ya tienen ese estado. Devuelve cuántas cambiaron.
- `alertas_pendientes(desde: date) -> (en_rango, anteriores)`: listas con lo que pide la tabla y el detalle.
- `alertas_decididas(estado=None)` e `historial(alerta_id)`.
- `registrar_decision` (la ruta del Excel) recibe además la fecha y hora del reporte del que sale la decisión (`ahora` con que se escribió; se puede leer de la hoja Resumen, celda "Fecha", o del nombre del archivo). Aplica solo si la alerta está Pendiente **y** el reporte es posterior al último cambio registrado en `decision` para esa alerta. Si aplica, registra con `origen = 'excel'`. *(Criterio del diseño.)* Así:
  - un Excel viejo nunca pisa una corrección hecha en la ventana, incluida una devolución a Pendiente;
  - una alerta devuelta a Pendiente se puede decidir otra vez desde un reporte nuevo.
- Las decisiones del Excel que se ignoran por esta regla se cuentan y se avisan junto al aviso actual de decisiones aplicadas: "n decisión(es) de reportes anteriores se ignoraron porque la alerta se decidió después en la ventana."

`usuario` es `cfg["salida"]["validador"]`, igual que hoy en el Excel sin "Validó".

### 5.5 Regla de puesta al día

En `config.toml`, sección nueva, editable por Sistemas y no desde la ventana:

```toml
[alertas]
exigir_puesta_al_dia = false
umbral_anteriores = 30
objetivo_anteriores = 10
dias_corte_regla = 7
```

**La regla no usa el campo "días" de la ventana.** Para la regla, "anterior" es una alerta pendiente detectada antes de `hoy − dias_corte_regla`, con la misma convención de fechas de 5.1. Así no se puede esquivar subiendo el campo a 365. Las pestañas siguen usando el campo de la ventana. Si los dos valores no coinciden, el contador de la regla en el aviso rojo puede diferir del de la pestaña Anteriores; el aviso dice explícitamente "detectadas hace más de 7 días". *(Criterio del diseño: Luis aprobó el documento sin elegir entre las opciones planteadas; se tomó la recomendada. Alternativas descartadas: bloquear el campo mientras la obligación está activa, que no impide subirlo antes; o aceptar el hueco.)*

Comportamiento con `exigir_puesta_al_dia = true`:

- **Se activa** cuando, al abrir la ventana o al recargar la lista, las anteriores sin decidir (según `dias_corte_regla`) son **más de** `umbral_anteriores`. Queda guardado como obligación pendiente en la base (tabla de una fila o clave en una tabla de estado), para que cerrar a la fuerza no la borre.
- **Se libera** cuando las anteriores quedan **por debajo de** `objetivo_anteriores`.
- **Mientras está activa**: aviso rojo fijo arriba de las pestañas ("Hay 44 alertas anteriores sin decidir. Deben quedar menos de 10 antes de cerrar. Faltan 35."), la ventana abre en la pestaña Anteriores, y al cerrar sale un aviso solo con **Volver a revisar**. "Consultar ahora" no cambia.
- Un cierre forzado (Administrador de tareas, apagar el equipo) no se puede impedir; al volver a abrir, la obligación sigue.

Con `exigir_puesta_al_dia = false` (por defecto) no se activa nada y el cierre solo muestra el aviso de 5.6.

### 5.6 Al cerrar la ventana

`raiz.protocol("WM_DELETE_WINDOW", ...)`:

1. Si la obligación de 5.5 está activa: aviso sin opción de cerrar.
2. Si no, y hay pendientes en el rango: "Quedan n alertas por decidir de los últimos N días. ¿Cerrar de todas formas?" con **Volver a revisar** o **Cerrar igual**.
3. Si no hay pendientes: cierra como hoy.

Con una consulta en curso lanzada desde la ventana, los pasos 1 a 3 se aplican igual, en el mismo orden: una consulta en marcha no sirve para saltarse la obligación ni el aviso. Si al final la ventana se cierra, lo que le pasa a la consulta no cambia respecto de hoy (se corta y se reanuda en la siguiente). *(Criterio del diseño.)*

### 5.7 Reporte Excel

Sin cambios de formato. La columna Decisión muestra el estado vigente. Las alertas devueltas a Pendiente vuelven a aparecer como pendientes, como cualquier otra.

## 6. Dónde va cada cosa

| Módulo | Cambio |
|---|---|
| `store.py` | Tabla `decision`, migración, `decidir`, `alertas_pendientes`, `alertas_decididas`, `historial`, nueva regla en `registrar_decision`, estado de la obligación |
| `panel.py` | Lógica sin tkinter: separar en rango y anteriores, textos de contadores y avisos, decisión de qué hacer al cerrar, evaluación de la regla |
| `ventana.py` | Pestañas, tabla con casillas, botones, detalle, "Ver decididas", cierre |
| `main.py` | Leer `[alertas]` con valores por defecto; nada más |
| `config.example.toml`, `README.md`, bóveda | Documentar la sección `[alertas]`, cómo decidir y cómo encender la regla |

## 7. Pruebas

- `store`: decisión en bloque, corrección, vuelta a Pendiente, historial completo, migración idempotente, y un Excel viejo que no pisa una corrección.
- `panel`: frontera del rango (N = 0, N = 7, inclusive), activación por encima de 30, liberación por debajo de 10, persistencia de la obligación, qué hace el cierre en cada caso.
- `ventana`: con el mismo patrón de `tests/test_ventana.py` (se salta sin entorno gráfico). Seleccionar todas y confirmar; el refresco no borra la selección; cerrar con y sin pendientes; regla apagada y encendida.
- Las 263 pruebas actuales siguen pasando.

## 8. Lo que queda a criterio de quien construye

- El widget de la tabla (por ejemplo `ttk.Treeview` con una columna de casilla) y cómo se ve la casilla.
- El tamaño de la ventana y el desplazamiento cuando la lista es larga.
- Dónde guardar la obligación de la regla dentro de la base.
- Los textos exactos, mientras digan lo mismo que este documento.

## 9. Entrega

- Rama nueva desde `master`, PR al repositorio `luisfajardo-bot/consultor-judicial`, con commits y push desde la cuenta **luisfajardo-bot**. Antes de subir hay que configurar en este Mac la identidad de git y la autenticación de esa cuenta.
- Al terminar, quien mantiene la herramienta actualiza el equipo de Alisson con `scripts\actualizar.bat`.
