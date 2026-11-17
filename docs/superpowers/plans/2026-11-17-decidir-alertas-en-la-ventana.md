# Decidir alertas desde la ventana: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Alisson confirme o descarte alertas desde la ventana, varias a la vez, con historial completo de cada decisión y corrección, aviso al cerrar y una regla de puesta al día que se construye apagada.

**Architecture:** Tabla nueva `decision` (solo se agregan filas) y tabla `estado_app` en SQLite, con métodos en `Store`. La lógica sin tkinter (qué pestaña, qué texto, qué hacer al cerrar, la regla) va en `panel.py` como funciones puras. `ventana.py` solo pinta y llama. La ruta del Excel sigue viva, pero respeta lo decidido después en la ventana.

**Tech Stack:** Python ≥ 3.11, tkinter/ttk, sqlite3, openpyxl 3.1.5, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-11-17-decidir-alertas-en-la-ventana-design.md`

## Global Constraints

- Sin dependencias nuevas: solo `requests`, `openpyxl` y la biblioteca estándar.
- Python ≥ 3.11. Sin modo WAL de SQLite.
- Todo texto visible y todo nombre nuevo, en español, con el estilo del código actual.
- `panel.py` no importa tkinter; `ventana.py` no contiene reglas, solo pinta.
- "Consultar ahora" nunca se bloquea por alertas sin decidir.
- Nada se borra de `decision`; cada cambio de `alerta.estado` inserta su fila en la misma transacción.
- `[alertas]` por defecto: `exigir_puesta_al_dia = false`, `umbral_anteriores = 30`, `objetivo_anteriores = 10`, `dias_corte_regla = 7`.
- Pruebas: `python -m pytest` desde la raíz del repo, con un entorno que tenga `requirements-dev.txt`. En esta sesión: `/private/tmp/claude-501/-Users-luisfajardobravo-ICEIN-consultor-judicial/b1f2d6d1-207c-46a9-ba5f-b7a364758429/scratchpad/venv/bin/python -m pytest`. Las 263 pruebas actuales deben seguir pasando, salvo las que este plan modifica a propósito (Task 2).
- Commits en la rama `feat/decidir-alertas-en-la-ventana`, con autor `LUIS FERNANDO FAJARDO BRAVO <luisfajardo@indugravas.com>` (ya configurado en el repo) y el pie `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nada de push sin confirmación de Luis.

Textos exactos (fijados por el spec o por este plan):

| Clave | Texto |
|---|---|
| Pestaña rango | `Por decidir · últimos {dias} días ({n})`; con `dias == 0`: `Por decidir · hoy ({n})` |
| Pestaña anteriores | `Anteriores sin decidir ({n})` |
| Lista vacía | `Al día ✓` |
| Ayuda | `Confirmar = la actuación es real y ya la revisé en el portal. Descartar = no requiere acción (repetida, trámite sin efecto, error).` |
| Etiqueta días | `Días a revisar: avisar lo registrado en los últimos` [campo] `días (también define la pestaña Por decidir)` |
| Guardado N>0 | `Guardado: {d} días. La pestaña Por decidir ya muestra los últimos {d} días; en radicados nuevos rige desde la próxima consulta.` |
| Guardado 0 | `Guardado: 0 días. No se avisará nada en radicados nuevos; Por decidir muestra solo lo detectado hoy.` |
| Confirmar en bloque (>5) | `¿{Confirmar\|Descartar} {n} alertas? Se puede corregir desde Ver decididas.` |
| Sin selección | `Seleccione al menos una alerta.` |
| Base ocupada | `La base está ocupada por una consulta; intente de nuevo en unos segundos.` |
| Portal | `Radicado copiado` |
| Cierre con pendientes | `Quedan {n} alertas por decidir de los últimos {dias} días. ¿Cerrar de todas formas?` |
| Obligación (aviso rojo y cierre) | `Hay {n} alertas anteriores sin decidir (detectadas hace más de {dias_corte} días). Deben quedar menos de {objetivo} antes de cerrar. Faltan {n - objetivo + 1}.` |
| Excel ignorado | `{n} decisión(es) de reportes anteriores se ignoraron porque la alerta se decidió después en la ventana.` |

## Review Focus

1. **Decidir mientras corre una consulta**: el ciclo escribe en la base y la ventana también. Si SQLite responde "database is locked", se espera el texto "Base ocupada", sin caerse y sin perder la selección. Prueba en Task 4.
2. **Pulsar Confirmar o Descartar sin nada seleccionado**: se espera "Seleccione al menos una alerta." y que no cambie nada. Prueba en Task 4.
3. **Alerta cuya consulta de origen no existe** (base vieja o editada a mano): la fecha de detección cae en `ciclo.inicio` y la alerta aparece igual. Prueba en Task 3.
4. **Reporte sin celda "Fecha" en Resumen** (reporte ajeno o dañado): la decisión se aplica solo si la alerta nunca tuvo historial; nunca pisa una corrección. Prueba en Task 2.
5. **Días = 0 y fronteras del rango**: lo detectado hoy va a "Por decidir"; lo de ayer va a "Anteriores". Prueba en Task 3.

---

### Task 1: Historial de decisiones en la base

**Files:**
- Modify: `consultor/store.py` (ESQUEMA, `__init__`, métodos nuevos)
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  - Constantes en `store.py`: `ORIGEN_VENTANA = "ventana"`, `ORIGEN_EXCEL = "excel"`, `ORIGEN_MIGRACION = "migracion"`.
  - `Store.decidir(self, alerta_ids: Iterable[int], estado: str, usuario: str, ahora: datetime, origen: str = ORIGEN_VENTANA) -> int`: estados válidos `CONFIRMADA`, `DESCARTADA`, `PENDIENTE` (otro lanza `ValueError`). Una transacción para todas. Salta las que ya tienen ese estado o no existen. Por cada cambio: actualiza `alerta.estado`, `validada_por` y `validada_en` (a `NULL` las dos últimas si vuelve a `PENDIENTE`) e inserta en `decision`. Devuelve cuántas cambiaron.
  - `Store.historial(self, alerta_id: int) -> list[dict]`: claves `estado_anterior`, `estado_nuevo`, `usuario`, `momento` (str ISO), `origen`, en orden de `decision.id`.
  - `Store.obligacion_activa(self) -> bool` y `Store.fijar_obligacion(self, activa: bool) -> None`, sobre `estado_app(clave TEXT PRIMARY KEY, valor TEXT NOT NULL)` con clave `obligacion_puesta_al_dia` y valor `"1"` o `"0"` (falta = `False`).

- [ ] **Step 1: Write the failing tests**

```python
def test_decidir_en_bloque_cambia_estado_y_deja_historial(store):
    ids = _dos_alertas(store)                       # helper nuevo: crea 2 alertas Pendiente
    assert store.decidir(ids, CONFIRMADA, "Alisson", AHORA) == 2
    assert store.contar_pendientes() == 0
    h = store.historial(ids[0])
    assert [(x["estado_anterior"], x["estado_nuevo"], x["usuario"], x["origen"]) for x in h] == [
        (PENDIENTE, CONFIRMADA, "Alisson", "ventana")]

def test_corregir_y_volver_a_pendiente_acumula_historial(store):
    (a, _) = _dos_alertas(store)
    store.decidir([a], DESCARTADA, "Alisson", AHORA)
    store.decidir([a], CONFIRMADA, "Alisson", AHORA + timedelta(minutes=1))
    store.decidir([a], PENDIENTE, "Alisson", AHORA + timedelta(minutes=2))
    assert [x["estado_nuevo"] for x in store.historial(a)] == [DESCARTADA, CONFIRMADA, PENDIENTE]
    f = store.con.execute("SELECT estado, validada_por, validada_en FROM alerta WHERE id=?", (a,)).fetchone()
    assert tuple(f) == (PENDIENTE, None, None)

def test_decidir_al_mismo_estado_no_agrega_historial(store):
    (a, _) = _dos_alertas(store)
    store.decidir([a], DESCARTADA, "Alisson", AHORA)
    assert store.decidir([a], DESCARTADA, "Alisson", AHORA) == 0
    assert len(store.historial(a)) == 1

def test_decidir_estado_invalido_lanza_error(store):
    with pytest.raises(ValueError):
        store.decidir([1], "Quizás", "Alisson", AHORA)

def test_migracion_crea_historial_de_lo_ya_decidido_una_sola_vez(tmp_path):
    ruta = tmp_path / "c.db"
    s = Store(ruta); (a, _) = _dos_alertas(s)
    s.con.execute("UPDATE alerta SET estado=?, validada_por='Ana', validada_en=? WHERE id=?", (DESCARTADA, AHORA.isoformat(), a))
    s.con.execute("DELETE FROM decision"); s.con.commit(); s.con.close()   # simula base anterior al cambio
    for _ in range(2):
        s = Store(ruta)
        assert [(x["estado_nuevo"], x["usuario"], x["origen"]) for x in s.historial(a)] == [(DESCARTADA, "Ana", "migracion")]
        s.con.close()

def test_obligacion_se_guarda_y_por_defecto_es_falsa(store):
    assert store.obligacion_activa() is False
    store.fijar_obligacion(True);  assert store.obligacion_activa() is True
    store.fijar_obligacion(False); assert store.obligacion_activa() is False
```

`_dos_alertas(store) -> tuple[int, int]` crea un ciclo con dos actuaciones nuevas (como `_con_novedad`, que ya existe) y devuelve sus `alerta.id`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_store.py -k "decidir or historial or migracion or obligacion" -v`
Expected: FAIL con `AttributeError: 'Store' object has no attribute 'decidir'`.

- [ ] **Step 3: Implement**

Agrega `decision`, su índice `ix_decision_alerta` y `estado_app` al ESQUEMA, tal como dice el spec en 5.4. La migración va en `__init__`, después de la actual: inserta con `origen='migracion'` una fila por cada alerta con estado distinto de Pendiente que no tenga filas en `decision`. Usa `INSERT ... SELECT ... WHERE NOT EXISTS`, así es idempotente y resiste cortes. Para `momento` usa `validada_en`, o `ciclo.inicio` si falta, y para `usuario` usa `validada_por`, o `''` si falta.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_store.py -v`
Expected: PASS, incluidas las pruebas anteriores de `test_store.py`.

- [ ] **Step 5: Commit**

```bash
git add consultor/store.py tests/test_store.py
git commit -m "feat: historial de decisiones y decisión en bloque en la base"
```

---

### Task 2: El Excel respeta lo decidido después en la ventana

**Files:**
- Modify: `consultor/reporter.py:118-158` (`leer_decisiones`)
- Modify: `consultor/store.py:329-341` (`registrar_decision`)
- Modify: `consultor/main.py:62-66`
- Test: `tests/test_reporter.py`, `tests/test_store.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `Store.decidir`, `Store.historial`, `ORIGEN_EXCEL` (Task 1).
- Produces:
  - `leer_decisiones(carpeta, avisar_fn=None) -> list[tuple[int, str, str, datetime | None]]`. El cuarto elemento es la fecha y hora de la fila "Fecha" de la hoja Resumen (`"%Y-%m-%d %H:%M"`), o `None` si falta o no se puede leer.
  - Constantes en `store.py`: `EXCEL_APLICADA = "aplicada"`, `EXCEL_IGNORADA = "ignorada"`, `EXCEL_SIN_EFECTO = "sin_efecto"`.
  - `Store.registrar_decision(self, alerta_id: int, estado: str, usuario: str, ahora: datetime, fecha_reporte: datetime | None = None) -> str`. Con `estado` inválido lanza `ValueError`. Si la alerta no está Pendiente devuelve `EXCEL_SIN_EFECTO`. Si está Pendiente y tiene historial, y además `fecha_reporte` es `None` o no es posterior a su último `decision.momento`, devuelve `EXCEL_IGNORADA`. En cualquier otro caso llama a `decidir([alerta_id], estado, usuario, ahora, ORIGEN_EXCEL)` y devuelve `EXCEL_APLICADA`.

- [ ] **Step 1: Write the failing tests**

En `tests/test_store.py`, reemplaza `test_decision_solo_desde_pendiente_y_se_conserva_la_primera` por:

```python
def test_excel_aplica_solo_sobre_pendiente(store):
    c2 = _con_novedad(store); a = store.filas_reporte(c2)[0]["alerta_id"]
    assert store.registrar_decision(a, DESCARTADA, "Alisson", AHORA) == EXCEL_APLICADA
    assert store.registrar_decision(a, CONFIRMADA, "Otra", AHORA) == EXCEL_SIN_EFECTO
    assert store.historial(a)[-1]["origen"] == "excel"

def test_excel_viejo_no_pisa_una_vuelta_a_pendiente_hecha_en_la_ventana(store):
    c2 = _con_novedad(store); a = store.filas_reporte(c2)[0]["alerta_id"]
    store.decidir([a], CONFIRMADA, "Alisson", AHORA)
    store.decidir([a], PENDIENTE, "Alisson", AHORA + timedelta(hours=1))
    assert store.registrar_decision(a, DESCARTADA, "Alisson", AHORA + timedelta(hours=2),
                                    fecha_reporte=AHORA) == EXCEL_IGNORADA
    assert store.registrar_decision(a, DESCARTADA, "Alisson", AHORA + timedelta(hours=2),
                                    fecha_reporte=AHORA + timedelta(hours=1, minutes=5)) == EXCEL_APLICADA

def test_excel_sin_fecha_no_pisa_una_alerta_con_historial(store):          # Review Focus 4
    c2 = _con_novedad(store); a = store.filas_reporte(c2)[0]["alerta_id"]
    store.decidir([a], CONFIRMADA, "Alisson", AHORA); store.decidir([a], PENDIENTE, "Alisson", AHORA)
    assert store.registrar_decision(a, DESCARTADA, "Alisson", AHORA, fecha_reporte=None) == EXCEL_IGNORADA
```

En `tests/test_reporter.py`, las aserciones existentes de `leer_decisiones` pasan a 4-tuplas, con la fecha del reporte que escribe la prueba (`ahora` del `escribir_reporte` de cada prueba, sin segundos). Agrega una prueba más: si se borra la fila "Fecha" de Resumen, el cuarto elemento es `None`.

En `tests/test_main.py`:

```python
def test_el_ciclo_avisa_las_decisiones_del_excel_ignoradas(tmp_path):
    # ciclo 1 crea una alerta y su reporte; en la ventana se confirma y se devuelve a Pendiente;
    # el reporte viejo dice "Descartada": el ciclo siguiente no la aplica y lo avisa
    ...
    assert any("1 decisión(es) de reportes anteriores se ignoraron" in a for a in avisos)
    assert store.historial(alerta_id)[-1]["estado_nuevo"] == PENDIENTE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_store.py tests/test_reporter.py tests/test_main.py -v`
Expected: FAIL. Las comparaciones contra `EXCEL_*` fallan porque hoy `registrar_decision` devuelve `bool`, y las 4-tuplas no coinciden.

- [ ] **Step 3: Implement**

- `leer_decisiones` lee la fila cuya primera celda es `"Fecha"` de la hoja `Resumen`, con `datetime.strptime(valor, "%Y-%m-%d %H:%M")`, y la pone como cuarto elemento de cada tupla de ese archivo. Si falta o no se puede leer, usa `None`.
- `registrar_decision` sigue lo que dice el bloque Interfaces.
- En `main.correr_ciclo`, cuenta los `EXCEL_APLICADA` (el aviso actual no cambia) y los `EXCEL_IGNORADA` (avísalos con el texto "Excel ignorado" de Global Constraints).

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: todo PASS.

- [ ] **Step 5: Commit**

```bash
git add consultor/reporter.py consultor/store.py consultor/main.py tests/
git commit -m "feat: una decisión del Excel no pisa lo corregido después en la ventana"
```

---

### Task 3: Consultas de alertas y lógica de la pantalla (sin tkinter)

**Files:**
- Modify: `consultor/store.py` (dos métodos de lectura)
- Modify: `consultor/panel.py` (funciones puras)
- Test: `tests/test_store.py`, `tests/test_panel.py`

**Interfaces:**
- Consumes: `Store.decidir`, `Store.obligacion_activa` (Task 1).
- Produces:
  - `Store.alertas_pendientes(self) -> list[dict]`: claves `id`, `radicado`, `ciclo_id`, `detectada` (str ISO: `consulta.hora` del ciclo y radicado de la alerta, o `ciclo.inicio` si falta), `fecha_actuacion`, `actuacion`, `anotacion`, `despacho` (como en `PENDIENTES_SQL`). Orden: `detectada` descendente y `id` descendente.
  - `Store.alertas_decididas(self, estado: str | None = None) -> list[dict]`: claves `id`, `radicado`, `estado`, `validada_por`, `validada_en`, `fecha_actuacion`, `actuacion`. Filtra por `estado` si viene. Orden: `validada_en` descendente.
  - En `panel.py`:
    - `@dataclass(frozen=True) class ConfigAlertas: exigir: bool = False; umbral: int = 30; objetivo: int = 10; dias_corte: int = 7`
    - `config_alertas(cfg: dict) -> ConfigAlertas`: lee `cfg.get("alertas", {})` con las claves `exigir_puesta_al_dia`, `umbral_anteriores`, `objetivo_anteriores`, `dias_corte_regla`.
    - `separar(pendientes: list[dict], hoy: date, dias: int) -> tuple[list[dict], list[dict]]`: devuelve `(en_rango, anteriores)`. Una alerta va en rango si `date(detectada) >= hoy - timedelta(days=dias)`. Conserva el orden.
    - `contar_para_regla(pendientes: list[dict], hoy: date, c: ConfigAlertas) -> int`: cuenta con `separar(..., c.dias_corte)[1]`.
    - `evaluar_obligacion(activa: bool, anteriores: int, c: ConfigAlertas) -> bool`: si `not c.exigir`, `False`. Si `anteriores > c.umbral`, `True`. Si `anteriores < c.objetivo`, `False`. En otro caso, `activa`.
    - `@dataclass(frozen=True) class AccionCierre: tipo: str; texto: str = ""`, donde `tipo` es `"bloquear"`, `"preguntar"` o `"cerrar"`.
    - `accion_al_cerrar(obligacion: bool, anteriores_regla: int, en_rango: int, dias: int, c: ConfigAlertas) -> AccionCierre`: si hay obligación, `bloquear` con el texto de obligación. Si no, y `en_rango > 0`, `preguntar` con el texto de cierre. Si no, `cerrar`.
    - `texto_pestana_rango(dias: int, n: int) -> str`, `texto_pestana_anteriores(n: int) -> str`, `texto_obligacion(n: int, c: ConfigAlertas) -> str`, `texto_dias_guardado(dias: int) -> str`, `texto_confirmar_bloque(estado: str, n: int) -> str`. Todos con los textos exactos de Global Constraints.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
def test_alertas_pendientes_trae_fecha_de_deteccion_y_excluye_decididas(store):
    (a, b) = _dos_alertas(store)
    store.decidir([b], DESCARTADA, "Alisson", AHORA)
    p = store.alertas_pendientes()
    assert [x["id"] for x in p] == [a]
    assert p[0]["detectada"].startswith(AHORA.date().isoformat())

def test_alerta_sin_consulta_de_origen_usa_el_inicio_del_ciclo(store):            # Review Focus 3
    (a, _) = _dos_alertas(store)
    store.con.execute("DELETE FROM consulta"); store.con.commit()
    assert {x["id"] for x in store.alertas_pendientes()} >= {a}

def test_alertas_decididas_filtra_por_estado(store):
    (a, b) = _dos_alertas(store)
    store.decidir([a], CONFIRMADA, "Alisson", AHORA); store.decidir([b], DESCARTADA, "Alisson", AHORA)
    assert [x["id"] for x in store.alertas_decididas(CONFIRMADA)] == [a]
    assert len(store.alertas_decididas()) == 2

# tests/test_panel.py
HOY = date(2026, 11, 17)
def _p(*dias_atras): return [{"id": i, "detectada": f"{HOY - timedelta(days=d)}T08:00:00"} for i, d in enumerate(dias_atras)]

def test_separar_frontera_inclusiva():
    en, ant = separar(_p(0, 7, 8), HOY, 7)
    assert [x["id"] for x in en] == [0, 1] and [x["id"] for x in ant] == [2]

def test_separar_con_cero_dias_deja_solo_hoy():                                   # Review Focus 5
    en, ant = separar(_p(0, 1), HOY, 0)
    assert [x["id"] for x in en] == [0] and [x["id"] for x in ant] == [1]

def test_evaluar_obligacion_se_activa_sobre_30_y_se_libera_bajo_10():
    c = ConfigAlertas(exigir=True)
    assert evaluar_obligacion(False, 30, c) is False
    assert evaluar_obligacion(False, 31, c) is True
    assert evaluar_obligacion(True, 10, c) is True
    assert evaluar_obligacion(True, 9, c) is False
    assert evaluar_obligacion(True, 50, ConfigAlertas(exigir=False)) is False

def test_la_regla_usa_su_propio_corte_y_no_el_campo_dias():
    p = _p(*([20] * 31))
    assert contar_para_regla(p, HOY, ConfigAlertas(exigir=True, dias_corte=7)) == 31

def test_accion_al_cerrar():
    c = ConfigAlertas(exigir=True)
    assert accion_al_cerrar(True, 44, 3, 7, c).tipo == "bloquear"
    assert "Faltan 35." in accion_al_cerrar(True, 44, 3, 7, c).texto
    a = accion_al_cerrar(False, 0, 3, 7, c)
    assert a.tipo == "preguntar" and a.texto == "Quedan 3 alertas por decidir de los últimos 7 días. ¿Cerrar de todas formas?"
    assert accion_al_cerrar(False, 0, 0, 7, c).tipo == "cerrar"

def test_config_alertas_por_defecto_apagada():
    assert config_alertas({}) == ConfigAlertas(False, 30, 10, 7)

def test_textos_de_pestanas_y_guardado():
    assert texto_pestana_rango(7, 5) == "Por decidir · últimos 7 días (5)"
    assert texto_pestana_rango(0, 2) == "Por decidir · hoy (2)"
    assert texto_dias_guardado(0).startswith("Guardado: 0 días. No se avisará nada")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_store.py tests/test_panel.py -v`
Expected: FAIL con `ImportError` o `AttributeError` por los nombres nuevos.

- [ ] **Step 3: Implement** los métodos y funciones del bloque Interfaces. Para `detectada`, el SQL usa `COALESCE(c.hora, ci.inicio)` con un `LEFT JOIN consulta c ON c.ciclo_id = a.ciclo_id AND c.radicado = a.radicado` y un `JOIN ciclo ci ON ci.id = a.ciclo_id`.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: todo PASS.

- [ ] **Step 5: Commit**

```bash
git add consultor/store.py consultor/panel.py tests/test_store.py tests/test_panel.py
git commit -m "feat: lógica de pestañas, regla de puesta al día y cierre, sin tkinter"
```

---

### Task 4: Lista de alertas en la ventana con decisión en bloque

**Files:**
- Modify: `consultor/ventana.py`
- Test: `tests/test_ventana.py`

**Interfaces:**
- Consumes: `Store.alertas_pendientes`, `Store.decidir` (Tasks 1 y 3); `separar`, `texto_pestana_*`, `texto_dias_guardado`, `texto_confirmar_bloque` (Task 3); `ENLACE_PORTAL` de `reporter.py`.
- Produces (los usan las Tasks 5 y 6 y sus pruebas):
  - `Ventana.__init__(self, raiz, cfg, ejecutar=ejecutar_ciclo, confirmar=None, preguntar=None, informar=None, hoy=date.today)`. `preguntar(titulo, texto) -> bool` usa por defecto `messagebox.askyesno`; `informar(titulo, texto) -> None` usa por defecto `messagebox.showwarning`.
  - Atributos: `self.pestanas` (`ttk.Notebook`), `self.tabla_rango` y `self.tabla_anteriores` (`ttk.Treeview`, iid = `str(alerta_id)`), `self.marcadas: set[int]`, `self.etiqueta_detalle`, `self.etiqueta_alertas` (mensajes de esta zona), `self.boton_todas`, `self.boton_confirmar`, `self.boton_descartar`, `self.boton_decididas`, `self.boton_portal`.
  - Métodos: `recargar_alertas() -> None`, `alternar_marca(alerta_id: int) -> None`, `seleccionar_todas() -> None` (marca todas las de la pestaña visible o, si ya están todas, las desmarca), `aplicar(estado: str) -> int` (devuelve cuántas cambiaron), `abrir_portal() -> None`.

- [ ] **Step 1: Write the failing tests**

El patrón de fixtures `raiz` y `_cfg` ya existe en `tests/test_ventana.py`. Agrega dos helpers que usan las Tasks 4 a 6:
- `_con_alertas(cfg, hoy: int = 0, hace_20_dias: int = 0) -> list[int]`: crea esa cantidad de alertas Pendiente con `Store` sobre `cfg["salida"]["base_datos"]`. La consulta de origen tiene `hora` igual a `HOY`, o a `HOY − 20 días`. Devuelve los ids, primero las de hoy.
- `_decidir(cfg, ids, estado=CONFIRMADA) -> None`: llama a `Store(...).decidir(ids, estado, "Alisson", datetime.now())` y cierra la conexión.

```python
def test_las_pestanas_separan_rango_y_anteriores(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch); _con_alertas(cfg, hoy=2, hace_20_dias=3)
    v = Ventana(raiz, cfg, hoy=lambda: HOY); v.recargar_alertas()
    assert len(v.tabla_rango.get_children()) == 2 and len(v.tabla_anteriores.get_children()) == 3
    assert v.pestanas.tab(0, "text") == "Por decidir · últimos 7 días (2)"

def test_seleccionar_todas_y_confirmar_deja_la_pestana_al_dia(raiz, tmp_path, monkeypatch):
    ...; v.seleccionar_todas(); assert v.aplicar(CONFIRMADA) == 2
    assert v.tabla_rango.get_children() == () and "Al día ✓" in v.etiqueta_alertas.cget("text")

def test_mas_de_cinco_pide_confirmacion_y_si_no_se_confirma_no_cambia(raiz, tmp_path, monkeypatch):
    preguntas = []
    v = Ventana(raiz, cfg, hoy=lambda: HOY, preguntar=lambda t, x: preguntas.append(x) or False)  # 6 en rango
    v.recargar_alertas(); v.seleccionar_todas()
    assert v.aplicar(DESCARTADA) == 0 and preguntas == ["¿Descartar 6 alertas? Se puede corregir desde Ver decididas."]

def test_sin_seleccion_avisa_y_no_cambia(raiz, tmp_path, monkeypatch):                  # Review Focus 2
    ...; assert v.aplicar(CONFIRMADA) == 0
    assert v.etiqueta_alertas.cget("text") == "Seleccione al menos una alerta."

def test_con_la_base_ocupada_avisa_y_conserva_la_seleccion(raiz, tmp_path, monkeypatch):  # Review Focus 1
    ...; v.seleccionar_todas()
    otra = sqlite3.connect(cfg["salida"]["base_datos"], timeout=0); otra.execute("BEGIN EXCLUSIVE")
    assert v.aplicar(CONFIRMADA) == 0                      # busy_timeout de 2 s (Step 3) y luego el aviso
    assert v.etiqueta_alertas.cget("text").startswith("La base está ocupada")
    assert v.marcadas; otra.rollback(); otra.close()

def test_el_refresco_de_cada_segundo_no_borra_las_marcas(raiz, tmp_path, monkeypatch):
    ...; v.alternar_marca(ids[0]); v.sondear(); assert v.marcadas == {ids[0]}

def test_guardar_dias_recarga_las_pestanas_y_explica_las_dos_cosas(raiz, tmp_path, monkeypatch):
    ...; v.dias.set("30"); v.guardar_dias()
    assert len(v.tabla_rango.get_children()) == 5
    assert "La pestaña Por decidir ya muestra los últimos 30 días" in v.etiqueta_ajuste.cget("text")

def test_abrir_en_el_portal_copia_el_radicado(raiz, tmp_path, monkeypatch):
    abiertos = []; monkeypatch.setattr("webbrowser.open", abiertos.append)
    ...; v.tabla_rango.focus(str(ids[0])); v.abrir_portal()
    assert abiertos == [ENLACE_PORTAL] and raiz.clipboard_get() == RADICADO
```

`HOY` es una fecha fija. El helper deja los `detectada` relativos a ella.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ventana.py -v`
Expected: FAIL con `TypeError` por el argumento `hoy` y `AttributeError` por los atributos nuevos.

- [ ] **Step 3: Implement**

- Layout según el boceto A del spec (5.2): Notebook con dos pestañas, ayuda, botones, `Treeview` con columnas `marca`, `Detectada` (`dd-mmm`), `Radicado`, `Fecha actuación`, `Actuación`, y detalle debajo.
- Un clic en la columna `marca` llama a `alternar_marca`, que alterna `☐`/`☑`. El foco de fila actualiza el detalle: radicado completo, despacho, actuación, anotación y ciclo.
- `recargar_alertas` repinta y conserva `self.marcadas ∩ ids presentes`. Se llama solo en los casos de 5.3 del spec. `sondear()` compara `store.ultimo_ciclo()["id"]` con el último visto y solo recarga si cambió.
- `aplicar` usa `Store(ruta)` con `con.execute("PRAGMA busy_timeout = 2000")`. Ante `sqlite3.OperationalError` muestra el texto "Base ocupada" y no toca `marcadas`. `usuario` es `cfg["salida"]["validador"]`.
- `guardar_dias` usa `texto_dias_guardado` y llama a `recargar_alertas`.
- Cambia la etiqueta de días al texto de Global Constraints.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: todo PASS. Las pruebas existentes de la ventana siguen pasando.

- [ ] **Step 5: Commit**

```bash
git add consultor/ventana.py tests/test_ventana.py
git commit -m "feat: lista de alertas en la ventana con decisión en bloque"
```

---

### Task 5: Ver decididas y corregir

**Files:**
- Modify: `consultor/ventana.py`
- Test: `tests/test_ventana.py`

**Interfaces:**
- Consumes: `Store.alertas_decididas`, `Store.decidir`, `Store.historial`; `Ventana.recargar_alertas`.
- Produces: `Ventana.ver_decididas() -> VentanaDecididas` (abre un `tk.Toplevel` y devuelve el objeto). `VentanaDecididas` tiene `filtro: tk.StringVar` (`"Todas"`, `"Confirmada"` o `"Descartada"`), `tabla: ttk.Treeview` (iid = `str(alerta_id)`, selección múltiple), `etiqueta_historial`, `recargar() -> None` y `corregir(estado: str) -> int`. Al terminar, `corregir` llama a `recargar_alertas()` de la ventana principal.

- [ ] **Step 1: Write the failing tests**

```python
def test_corregir_una_descartada_a_pendiente_la_devuelve_a_la_lista(raiz, tmp_path, monkeypatch):
    ...; v.seleccionar_todas(); v.aplicar(DESCARTADA)
    d = v.ver_decididas(); d.tabla.selection_set(str(ids[0]))
    assert d.corregir(PENDIENTE) == 1
    assert str(ids[0]) in v.tabla_rango.get_children()

def test_filtrar_decididas_y_ver_historial(raiz, tmp_path, monkeypatch):
    ...; d = v.ver_decididas(); d.filtro.set("Confirmada"); d.recargar()
    assert set(d.tabla.get_children()) == {str(i) for i in confirmadas}
    d.tabla.selection_set(str(confirmadas[0])); d.tabla.event_generate("<<TreeviewSelect>>"); raiz.update()
    assert "Pendiente → Confirmada" in d.etiqueta_historial.cget("text")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ventana.py -k decididas -v`
Expected: FAIL con `AttributeError: 'Ventana' object has no attribute 'ver_decididas'`.

- [ ] **Step 3: Implement** según el bloque Interfaces y el spec (5.2, "Ver decididas"). Columnas: Decisión, Decidida en, Por, Radicado, Actuación. Botones: Confirmada, Descartada, Pendiente. El historial de la fila seleccionada va con una línea por cambio: `{momento} · {usuario} · {anterior} → {nuevo} ({origen})`.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: todo PASS.

- [ ] **Step 5: Commit**

```bash
git add consultor/ventana.py tests/test_ventana.py
git commit -m "feat: ver decididas y corregir con historial"
```

---

### Task 6: Cierre, regla de puesta al día y documentación

**Files:**
- Modify: `consultor/ventana.py` (`al_cerrar`, aviso rojo, `abrir`)
- Modify: `config.example.toml`, `README.md`, `vault/Módulos/panel y ventana.md`, `vault/Reglas de negocio.md`
- Test: `tests/test_ventana.py`

**Interfaces:**
- Consumes: `config_alertas`, `contar_para_regla`, `evaluar_obligacion`, `accion_al_cerrar`, `texto_obligacion` (Task 3); `Store.obligacion_activa` y `fijar_obligacion` (Task 1).
- Produces:
  - `Ventana.al_cerrar(self) -> str`: devuelve `"cerrada"`, `"bloqueada"` o `"cancelada"`. Solo con `"cerrada"` llama a `self.cerrar()`. `Ventana.__init__` recibe `cerrar=None`, que por defecto es `raiz.destroy`.
  - `Ventana.etiqueta_obligacion`: `tk.Label` roja, visible solo con la obligación activa.
  - `recargar_alertas` también evalúa y guarda la obligación con `evaluar_obligacion(store.obligacion_activa(), contar_para_regla(...), c)` y, si la obligación está activa, selecciona la pestaña Anteriores.
  - `abrir()` registra `raiz.protocol("WM_DELETE_WINDOW", v.al_cerrar)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cerrar_sin_pendientes_cierra(raiz, tmp_path, monkeypatch):
    cerrada = []; v = Ventana(raiz, cfg, hoy=lambda: HOY, cerrar=lambda: cerrada.append(1))
    assert v.al_cerrar() == "cerrada" and cerrada

def test_cerrar_con_pendientes_pregunta_y_respeta_la_respuesta(raiz, tmp_path, monkeypatch):
    ...  # 3 en rango; preguntar=lambda t, x: False  -> "cancelada"; con True -> "cerrada"

def test_regla_apagada_no_bloquea_aunque_haya_44_anteriores(raiz, tmp_path, monkeypatch):
    ...  # config sin [alertas]; 44 hace 20 días; nada en rango -> "cerrada"

def test_regla_encendida_bloquea_hasta_bajar_de_10_y_sobrevive_a_reabrir(raiz, tmp_path, monkeypatch):
    cfg["alertas"] = {"exigir_puesta_al_dia": True}; ...  # 44 hace 20 días
    v = Ventana(raiz, cfg, hoy=lambda: HOY, informar=lambda t, x: None, cerrar=lambda: None); v.recargar_alertas()
    assert v.al_cerrar() == "bloqueada"
    assert "Faltan 35." in v.etiqueta_obligacion.cget("text")
    _decidir(cfg, ids[:20])                                   # quedan 24: sigue activa aunque sea < 30
    v2 = Ventana(raiz, cfg, hoy=lambda: HOY, informar=lambda t, x: None, cerrar=lambda: None); v2.recargar_alertas()
    assert v2.al_cerrar() == "bloqueada"
    _decidir(cfg, ids[20:35]); v2.recargar_alertas()           # quedan 9
    assert v2.al_cerrar() == "cerrada"

def test_con_consulta_en_curso_el_cierre_sigue_las_mismas_reglas(raiz, tmp_path, monkeypatch):
    ...  # v.hilo = hilo vivo de prueba; regla encendida con 44 -> "bloqueada"

def test_consultar_ahora_no_se_bloquea_con_la_obligacion_activa(raiz, tmp_path, monkeypatch):
    ...; v.refrescar(); assert str(v.boton_consultar.cget("state")) == "normal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ventana.py -k "cerrar or regla or obligacion" -v`
Expected: FAIL con `AttributeError: 'Ventana' object has no attribute 'al_cerrar'`.

- [ ] **Step 3: Implement**

- `al_cerrar` sigue lo que devuelve `accion_al_cerrar`. Con `bloquear` llama a `informar("Alertas sin decidir", texto)`. Con `preguntar` llama a `preguntar("Alertas sin decidir", texto)`.
- Agrega la sección `[alertas]` a `config.example.toml` con los cuatro valores por defecto y un comentario: "Se enciende cuando lo indique la Gerencia Jurídica".
- En `README.md`, sección "Pantalla": cómo decidir desde la ventana, Ver decididas, qué hace el campo de días ahora y cómo encender la regla.
- En la bóveda: la tabla `decision`, el cambio a R6 (las decisiones se pueden corregir con historial) y la regla.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -q`
Expected: todo PASS.

- [ ] **Step 5: Commit**

```bash
git add consultor/ventana.py tests/test_ventana.py config.example.toml README.md vault/
git commit -m "feat: aviso al cerrar y regla de puesta al día (apagada); documentación"
```

---

### Task 7: Verificación y entrega

**Files:** ninguno nuevo.

- [ ] **Step 1: Suite completa**

Run: `python -m pytest -q`
Expected: todo PASS, con más pruebas que las 263 de partida.

- [ ] **Step 2: Probar con la copia real de la base, sin tocar el original**

Copia `consultor.db` a la carpeta temporal. Arma un `config.toml` temporal que apunte a esa copia y abre `python -m consultor ventana --config <temporal>`. Hay que ver 51 alertas repartidas entre las dos pestañas según los días. Luego confirma dos, corrígelas desde Ver decididas y comprueba que el historial muestre los cambios.

- [ ] **Step 3: Pedir a Luis confirmación para subir**

Con su visto bueno, desde la cuenta `luisfajardo-bot` (`gh auth status` debe mostrarla como activa):

```bash
git push -u origin feat/decidir-alertas-en-la-ventana
gh pr create --base master --title "Decidir alertas desde la ventana" --body "<resumen + enlace al spec y al plan>

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```
