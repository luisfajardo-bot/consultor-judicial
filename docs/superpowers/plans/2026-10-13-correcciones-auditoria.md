# Correcciones de la auditoría Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar los hallazgos de la auditoría del 2026-10-13 que pueden perder una novedad judicial en silencio o tumbar el monitoreo, más la higiene de datos y despliegue.

**Architecture:** Cambios pequeños y separados por módulo, cada uno con su prueba escrita antes. Se mantiene el diseño actual: el comparador sigue siendo puro, el fetcher es el único que conoce el portal y toda validación de la respuesta termina en `ERROR` (visible) y nunca en una consulta "Exitosa" con datos de menos.

**Tech Stack:** Python 3.11+, sqlite3, requests, openpyxl, tkinter, pytest.

**Fuera de este plan (decidido con Luis el 2026-10-13):**
- Hallazgo 2 (decisiones falsificables desde `reportes\`): la única usuaria es Alisson. Solo se conserva el aviso en el log de las decisiones importadas (Task 4).
- Hallazgo 7 (aviso activo y reintento tras bloqueo): necesita decidir con Sistemas el canal (correo, Teams) y la tarea programada.
- Hallazgo 14 (dependencias con hashes), 15 (panel abre la base cada segundo), 16 (rutas relativas): bajos, para después.
- **No usar `PYTHONSAFEPATH=1`** como sugirió la auditoría: con `python -m consultor` quita el directorio actual de `sys.path` y el paquete deja de encontrarse.

**Cómo correr las pruebas.** No hay `.venv` en el repo. Usa uno fuera de él:

```bash
python -m venv "$TEMP/venv" && "$TEMP/venv/Scripts/python" -m pip install -r requirements-dev.txt
cd /c/Users/Luis/Desktop/consultor-judicial && "$TEMP/venv/Scripts/python" -m pytest -q
```

Estado de partida: 202 pruebas en verde. Cada task termina con la suite completa en verde y un commit.

## Mapa de archivos

| Archivo | Responsabilidad | Tasks |
|---|---|---|
| `consultor/store.py` | Base SQLite: ids vistos, filas del reporte, último cierre | 1, 8 |
| `consultor/main.py` | Orquesta el ciclo: usa `ids_vistos`, avisa decisiones y filas sin radicado | 1, 4, 5 |
| `consultor/fetcher.py` | Valida la respuesta del portal | 2 |
| `consultor/comparator.py` | Actuación sin fecha cuenta como reciente | 3 |
| `consultor/reporter.py` | Lectura robusta de decisiones y guardado atómico | 4 |
| `consultor/loader.py` | Extracción de radicados y conteo de filas sin radicado | 5 |
| `.gitignore`, `scripts/ejecutar_ciclo.bat` | Higiene de datos y despliegue | 6 |
| `consultor/ventana.py` | La pantalla no se congela | 7 |
| `README.md`, `vault/*.md` | Documentación al día | 9 |

---

### Task 1: Un radicado no desaparece ni da alertas falsas cuando comparte actuaciones con otro (hallazgo 1)

**Causa.** `actuacion` guarda cada actuación bajo el primer radicado que la trajo, y `ids_conocidos(radicado)` solo mira ese radicado. Si dos radicados del cuadro devuelven el mismo proceso, el segundo nunca "conoce" nada: genera alertas falsas con todo su histórico y después, como la alerta ya existe, su fila deja de salir en el reporte.

**Files:**
- Modify: `consultor/store.py` (agregar `ids_vistos`, fila de respaldo en `filas_reporte`)
- Modify: `consultor/main.py` (usar `ids_vistos`)
- Test: `tests/test_store.py`, `tests/test_main.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

Al final de `tests/test_store.py`:

```python
def test_una_actuacion_vista_bajo_otro_radicado_no_es_nueva(store):
    c = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c, R.radicado, ok(act(1), act(2)), Veredicto(SIN_CAMBIO), "", AHORA)
    assert store.ids_vistos([1, 2, 3]) == {1, 2}
    assert store.ids_vistos([]) == set()
    assert store.ids_vistos(range(10_000, 10_700)) == set()  # más de un tramo de consulta


def test_una_novedad_sin_alerta_igual_sale_en_el_reporte(store):
    c = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(
        c, R.radicado, ok(act(1)), Veredicto(POSIBLE_NOVEDAD, nuevas=()), "", AHORA
    )
    filas = store.filas_reporte(c)
    assert [f["radicado"] for f in filas] == [R.radicado]
    assert "sin alerta" in filas[0]["motivo"]
```

Al final de `tests/test_main.py`:

```python
def _radicados_en(reporte):
    wb = load_workbook(reporte)
    salida = set()
    for hoja in ("Alertas", "Sin cambio"):
        filas = list(wb[hoja].iter_rows(values_only=True))
        i = filas[0].index("Radicado")
        salida |= {f[i] for f in filas[1:]}
    return salida


def test_dos_radicados_con_el_mismo_proceso_no_dan_alertas_falsas_ni_desaparecen(tmp_path):
    r2 = Radicado("11001400307720210114702")
    store, reloj = Store(":memory:"), Reloj()
    f = FetcherFalso({R1.radicado: ok(act(1), act(2)), r2.radicado: ok(act(1), act(2))})
    correr(tmp_path, [R1, r2], f, store, reloj)
    reloj.avanzar()
    ciclo2 = correr(tmp_path, [R1, r2], f, store, reloj)
    assert ciclo2.novedades == 0  # nada nuevo: ninguno de los dos alerta

    reloj.avanzar()
    nueva = ok(act(3), act(2), act(1))
    f.respuestas = {R1.radicado: nueva, r2.radicado: nueva}
    ciclo3 = correr(tmp_path, [R1, r2], f, store, reloj)
    assert store.con.execute("SELECT COUNT(*) FROM alerta").fetchone()[0] == 1  # una sola alerta
    assert _radicados_en(ciclo3.reporte) == {R1.radicado, r2.radicado}  # ninguno desaparece
```

- [ ] **Step 2: Verificar que fallan**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_store.py tests/test_main.py -q`
Expected: FAIL (`ids_vistos` no existe; el ciclo 2 reporta 1 o 2 novedades falsas).

- [ ] **Step 3: Implementar `ids_vistos` y la fila de respaldo en `consultor/store.py`**

Agregar debajo de `ids_conocidos`:

```python
    def ids_vistos(self, ids) -> set[int]:
        """Cuáles de estos ids ya están guardados, bajo cualquier radicado.

        El id de una actuación es único en todo el portal: si dos radicados devuelven el mismo
        proceso, lo que ya se vio bajo uno no es nuevo para el otro. Las marcas "?" son lo único
        que se arma con texto; los valores van como parámetros.
        """
        ids = list(ids)
        vistos: set[int] = set()
        for i in range(0, len(ids), 500):  # SQLite limita las variables por consulta
            tramo = ids[i : i + 500]
            marcas = ",".join("?" * len(tramo))
            filas = self.con.execute(
                f"SELECT id_reg_actuacion FROM actuacion WHERE id_reg_actuacion IN ({marcas})", tramo
            )
            vistos.update(f["id_reg_actuacion"] for f in filas)
        return vistos
```

En `filas_reporte`, reemplazar el bloque `if c["resultado"] == POSIBLE_NOVEDAD:` … `else: filas.append(base)` por:

```python
            if c["resultado"] == POSIBLE_NOVEDAD and alertas.get(c["radicado"]):
                for a in alertas[c["radicado"]]:
                    filas.append(
                        {
                            **base,
                            "alerta_id": a["id"],
                            "anterior": a["anterior"] or "",
                            "fecha_detectada": a["fecha_actuacion"],
                            "detectada": a["actuacion"],
                            "anotacion": a["anotacion"] or "",
                            "decision": a["estado"],
                            "validada_por": a["validada_por"] or "",
                            "validada_en": a["validada_en"] or "",
                        }
                    )
            elif c["resultado"] == POSIBLE_NOVEDAD:
                # red de seguridad: un radicado consultado nunca puede faltar en el reporte
                filas.append({**base, "motivo": "novedad sin alerta registrada: verificar en el portal"})
            else:
                filas.append(base)
```

- [ ] **Step 4: Usarlo en `consultor/main.py`**

Reemplazar

```python
            veredicto = comparar(
                consulta, store.ids_conocidos(r.radicado), store.tiene_referencia(r.radicado), desde
            )
```

por

```python
            veredicto = comparar(
                consulta,
                store.ids_vistos(a.id_reg_actuacion for a in consulta.actuaciones),
                store.tiene_referencia(r.radicado),
                desde,
            )
```

(`ids_conocidos` se conserva: lo usan las pruebas existentes.)

- [ ] **Step 5: Suite completa**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q`
Expected: PASS (204 pruebas).

- [ ] **Step 6: Commit**

```bash
git add consultor/store.py consultor/main.py tests/test_store.py tests/test_main.py
git commit -m "fix: un radicado que comparte actuaciones con otro no da alertas falsas ni desaparece del reporte"
```

---

### Task 2: El fetcher no devuelve "Exitosa" con datos de menos ni con datos raros (hallazgos 3, 11 y parte del 1)

**Causa.** La paginación solo mira `cant`: si falta o es menor que lo recibido, el ciclo se da por completo con actuaciones de menos. Un `idRegActuacion` nulo o de texto, o una fecha en otro formato, tampoco se detectan. Todo eso debe terminar en `ERROR` (aviso de posible cambio de la API).

**Files:**
- Modify: `consultor/fetcher.py` (`_actuacion`, `_actuaciones`, `consultar`)
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Arreglar el fixture existente y escribir las pruebas que fallan**

En `tests/test_fetcher.py`, el fixture `ACTUACIONES` no trae `cant` (el portal real sí). Agregar `"cant": 2,` a cada una de sus dos actuaciones (después de `"fechaRegistro"`).

Al final del archivo:

```python
def _con_actuaciones(lista):
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(200, {"actuaciones": lista})
    return rutas


def _a(**kw):
    base = {
        "idRegActuacion": 1,
        "fechaActuacion": "2026-10-08T00:00:00",
        "actuacion": "X",
        "anotacion": None,
        "fechaRegistro": "2026-10-08T00:00:00",
        "cant": 1,
    }
    base.update(kw)
    return base


@pytest.mark.parametrize("malo", [None, "17", True, 1.5])
def test_un_id_de_actuacion_que_no_es_entero_es_error_visible(malo):
    f, _, _ = crear(_con_actuaciones([_a(idRegActuacion=malo)]))
    assert f.consultar(RAD).estado == ERROR


@pytest.mark.parametrize("cant", [None, "1", 0])
def test_cant_inconsistente_es_error_visible(cant):
    f, _, _ = crear(_con_actuaciones([_a(cant=cant)]))
    assert f.consultar(RAD).estado == ERROR


def test_cant_ausente_es_error_visible():
    actuacion = _a()
    del actuacion["cant"]
    f, _, _ = crear(_con_actuaciones([actuacion]))
    assert f.consultar(RAD).estado == ERROR


@pytest.mark.parametrize("campo", ["fechaActuacion", "fechaRegistro"])
def test_una_fecha_con_otro_formato_es_error_visible(campo):
    f, _, _ = crear(_con_actuaciones([_a(**{campo: "08/10/2026"})]))
    assert f.consultar(RAD).estado == ERROR


def test_una_fecha_de_registro_vacia_sigue_siendo_exitosa():
    f, _, _ = crear(_con_actuaciones([_a(fechaRegistro=None)]))
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.actuaciones[0].fecha_registro == ""
```

- [ ] **Step 2: Verificar que fallan**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_fetcher.py -q`
Expected: FAIL en las pruebas nuevas (hoy devuelven EXITOSA).

- [ ] **Step 3: Implementar en `consultor/fetcher.py`**

Imports: agregar `from datetime import date` junto a `import re`.

Debajo de `_fecha`, agregar:

```python
def _entero(valor, campo: str) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise TypeError(f"{campo} no es un entero: {valor!r}")
    return valor


def _fecha_iso(valor) -> str:
    """Como _fecha, pero si hay texto exige AAAA-MM-DD: otro formato es un cambio de la API."""
    texto = _fecha(valor)
    if texto:
        date.fromisoformat(texto)  # ValueError si cambió el formato
    return texto
```

En `_actuacion`, cambiar tres líneas:

```python
        id_reg_actuacion=_entero(a["idRegActuacion"], "idRegActuacion"),
        ...
        fecha_actuacion=_fecha_iso(a["fechaActuacion"]),
        ...
        fecha_registro=_fecha_iso(a.get("fechaRegistro")),
```

En `_actuaciones`, reemplazar

```python
            total = max((a.get("cant") or 0 for a in lista), default=0)
            if not lista or len(acumuladas) >= total:
                break
```

por

```python
            cants = [a.get("cant") for a in lista]
            if any(not isinstance(c, int) or isinstance(c, bool) for c in cants):
                raise TypeError("actuaciones sin 'cant' entero")  # sin total no se sabe si falta algo
            total = max(cants, default=0)
            if len(acumuladas) > total:
                raise TypeError(f"cant ({total}) menor que las actuaciones recibidas ({len(acumuladas)})")
            if not lista or len(acumuladas) >= total:
                break
```

En `consultar`, ampliar el último `except`:

```python
        except (KeyError, TypeError, AttributeError, ValueError) as e:
```

- [ ] **Step 4: Suite completa**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q`
Expected: PASS. Si otra prueba falla porque su fixture no trae `cant`, agregarle `cant` igual al número de actuaciones: el portal real siempre lo manda.

- [ ] **Step 5: Digitos Unicode**

En `consultor/fetcher.py` cambiar `RADICADO_RE = re.compile(r"^\d{23}$")` por `re.compile(r"^[0-9]{23}$")`. Agregar la prueba:

```python
def test_digitos_unicode_no_son_un_radicado_valido():
    f, _, _ = crear(rutas_ok())
    c = f.consultar(Radicado("١" * 23))  # dígitos arábigos
    assert c.estado == FALLIDA
```

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_fetcher.py -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add consultor/fetcher.py tests/test_fetcher.py
git commit -m "fix: el portal con cant ausente, ids o fechas raros es ERROR visible y no Exitosa con datos de menos"
```

---

### Task 3: Una actuación sin ninguna fecha cuenta como reciente (hallazgo 11)

**Files:**
- Modify: `consultor/comparator.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Prueba que falla**

```python
def test_primera_consulta_actuacion_sin_ninguna_fecha_se_alerta():
    # sin fecha no se puede saber si es vieja: se avisa de más antes que callar
    v = comparar(ok(act(1, fecha="", registro="")), set(), False, desde="2026-10-07")
    assert v.resultado == POSIBLE_NOVEDAD
```

- [ ] **Step 2: Ver que falla**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_comparator.py -q` → FAIL.

- [ ] **Step 3: Implementar**

En `consultor/comparator.py`, sobre `comparar`, agregar:

```python
def _reciente(a, desde: str) -> bool:
    fecha = a.fecha_registro or a.fecha_actuacion
    return bool(desde) and (not fecha or fecha >= desde)
```

y reemplazar el cálculo de `recientes` por:

```python
        recientes = tuple(a for a in consulta.actuaciones if _reciente(a, desde))
```

- [ ] **Step 4: Suite y commit**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q` → PASS.

```bash
git add consultor/comparator.py tests/test_comparator.py
git commit -m "fix: en la primera consulta una actuación sin fecha se avisa en vez de callarse"
```

---

### Task 4: Un reporte dañado no tumba el ciclo; decisiones importadas quedan en el log; reporte atómico (hallazgos 4, 9, 12)

**Files:**
- Modify: `consultor/reporter.py` (`leer_decisiones`, `escribir_reporte`)
- Modify: `consultor/main.py` (aviso de decisiones aplicadas)
- Test: `tests/test_reporter.py`, `tests/test_main.py`

- [ ] **Step 1: Pruebas que fallan**

Al final de `tests/test_reporter.py` (agregar `import zipfile`, `import pytest`, `from openpyxl import Workbook` y `import consultor.reporter as reporter_mod` arriba si no están):

```python
def _libro(ruta, decisiones):
    wb = Workbook()
    ws = wb.active
    ws.title = "Alertas"
    ws.append(["ID alerta", "Decisión", "Validó"])
    for d in decisiones:
        ws.append(d)
    wb.save(ruta)


def _dañar_xml(ruta):
    tmp = ruta.with_name(ruta.name + ".copia")
    with zipfile.ZipFile(ruta) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            datos = zin.read(item.filename)
            if item.filename.startswith("xl/worksheets/"):
                datos = datos[: len(datos) // 2]  # XML truncado
            zout.writestr(item, datos)
    tmp.replace(ruta)


def test_un_reporte_con_xml_dañado_se_avisa_y_no_tumba_la_lectura(tmp_path):
    _libro(tmp_path / "reporte_a.xlsx", [[1, "Confirmada", "Ana"]])
    malo = tmp_path / "reporte_b.xlsx"
    _libro(malo, [[2, "Descartada", "Ana"]])
    _dañar_xml(malo)
    avisos = []
    assert leer_decisiones(tmp_path, avisos.append) == [(1, "Confirmada", "Ana")]
    assert any("reporte_b.xlsx" in a for a in avisos)


def test_un_reporte_demasiado_grande_se_salta_con_aviso(tmp_path, monkeypatch):
    _libro(tmp_path / "reporte_a.xlsx", [[1, "Confirmada", "Ana"]])
    monkeypatch.setattr(reporter_mod, "MAX_BYTES_REPORTE", 10)
    avisos = []
    assert leer_decisiones(tmp_path, avisos.append) == []
    assert any("demasiado grande" in a for a in avisos)


def test_si_falla_el_guardado_no_queda_un_reporte_a_medias(tmp_path, monkeypatch):
    def falla(self, ruta):
        open(ruta, "wb").write(b"PK parcial")
        raise OSError("disco lleno")

    monkeypatch.setattr(Workbook, "save", falla)
    with pytest.raises(OSError):
        escribir(tmp_path, [fila()])
    assert list(tmp_path.glob("reporte_*.xlsx")) == []
```

Al final de `tests/test_main.py`:

```python
def test_las_decisiones_importadas_quedan_en_el_aviso(tmp_path):
    avisos = []
    store, reloj, f, r1, r2 = dos_ciclos(tmp_path)
    wb = load_workbook(r2.reporte)
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    hoja.cell(row=2, column=enc.index("Decisión") + 1, value="Confirmada")
    wb.save(r2.reporte)
    reloj.avanzar()
    correr(tmp_path, [R1], f, store, reloj, avisos)
    assert any("1 decisión" in a and "reporte" in a.lower() for a in avisos)
```

- [ ] **Step 2: Ver que fallan**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_reporter.py tests/test_main.py -q` → FAIL.

- [ ] **Step 3: Implementar en `consultor/reporter.py`**

Imports: agregar `import os`. Constante debajo de `LEYENDA`:

```python
MAX_BYTES_REPORTE = 20 * 1024 * 1024  # un reporte real pesa unos cientos de KB
```

Reemplazar el cuerpo de `leer_decisiones` por:

```python
    decisiones = []
    for ruta in sorted(Path(carpeta).glob("reporte_*.xlsx")):
        try:
            if ruta.stat().st_size > MAX_BYTES_REPORTE:
                if avisar_fn:
                    avisar_fn(f"{ruta.name} es demasiado grande para ser un reporte; se salta.")
                continue
            de_este = []
            wb = load_workbook(ruta, read_only=True, data_only=True)
            try:
                filas = wb["Alertas"].iter_rows(values_only=True)
                enc = next(filas)
                i_id = enc.index("ID alerta")
                i_dec = enc.index("Decisión")
                i_val = enc.index("Validó")
                for f in filas:
                    if not (f[i_id] and f[i_dec] in (CONFIRMADA, DESCARTADA)):
                        continue
                    try:
                        alerta_id = int(f[i_id])
                    except (TypeError, ValueError):
                        if avisar_fn:
                            avisar_fn(f"ID de alerta inválido ({f[i_id]!r}) en {ruta.name}; fila ignorada.")
                        continue
                    de_este.append((alerta_id, f[i_dec], f[i_val] or ""))
            finally:
                wb.close()
            decisiones.extend(de_este)  # solo si el archivo se leyó completo
        except Exception as e:  # un archivo dañado no puede detener el monitoreo
            if avisar_fn:
                avisar_fn(
                    f"No se pudo leer {ruta.name} ({type(e).__name__}); "
                    "se reintenta en el próximo ciclo."
                )
    return decisiones
```

(El import `zipfile` queda sin uso en `leer_decisiones`; déjalo si otro código lo usa, o quítalo si `ruff`/la revisión lo marca.)

En `escribir_reporte`, reemplazar `wb.save(ruta)` por:

```python
    tmp = ruta.with_name(ruta.name + ".tmp")  # no termina en .xlsx: nadie lo lee como reporte
    try:
        wb.save(tmp)
        os.replace(tmp, ruta)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Aviso de decisiones en `consultor/main.py`**

Reemplazar

```python
    for alerta_id, decision, usuario in leer_decisiones(carpeta_reportes, avisar_fn):
        store.registrar_decision(alerta_id, decision, usuario or validador, ahora())
```

por

```python
    aplicadas = 0
    for alerta_id, decision, usuario in leer_decisiones(carpeta_reportes, avisar_fn):
        aplicadas += store.registrar_decision(alerta_id, decision, usuario or validador, ahora())
    if aplicadas:
        avisar_fn(f"Se registraron {aplicadas} decisión(es) tomadas en los reportes.")
```

- [ ] **Step 5: Suite y commit**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q` → PASS (si alguna prueba antigua asumía el último aviso, ajustar para buscar con `any(...)`).

```bash
git add consultor/reporter.py consultor/main.py tests/test_reporter.py tests/test_main.py
git commit -m "fix: un reporte dañado no tumba el ciclo, decisiones importadas en el aviso y guardado atómico"
```

---

### Task 5: El loader no pierde filas ni radicados en silencio (hallazgo 5)

**Files:**
- Modify: `consultor/loader.py`
- Modify: `consultor/main.py` (avisar filas sin radicado)
- Test: `tests/test_loader.py`, `tests/test_main.py`

- [ ] **Step 1: Pruebas que fallan**

Al final de `tests/test_loader.py`:

```python
@pytest.mark.parametrize(
    "celda",
    [
        "11001400307720210114700-2026",
        "11001400307720210114700.1",
        "11001400307720210114700 - 2",
        "11001400307720210114700 2026-01-15",
    ],
)
def test_un_radicado_pegado_a_otros_numeros_con_separador_se_conserva(tmp_path, celda):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[celda, "ICEIN", "", "", "Activo"]])
    assert [r.radicado for r in fuente(ruta).cargar()] == ["11001400307720210114700"]


def test_una_celda_numerica_se_marca_como_tal_y_no_como_un_numero_recortado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[1.10014003077202e22, "ICEIN", "", "", "Activo"]])
    (r,) = fuente(ruta).cargar()
    assert r.radicado.startswith("numérico:")


def test_cuenta_las_filas_con_datos_pero_sin_radicado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            [None, "ICEIN", "Juzgado 7", "", "Activo"],  # datos sin radicado
            [None, None, None, None, None],  # fila vacía: no cuenta
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
        ],
    )
    f = fuente(ruta)
    assert len(f.cargar()) == 1
    assert f.filas_sin_radicado == 1


def test_una_fila_sin_radicado_y_con_otro_estado_no_cuenta(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, "ICEIN", "", "", "Cerrado"]])
    f = fuente(ruta, estados_incluidos=["activo"])
    f.cargar()
    assert f.filas_sin_radicado == 0
```

Al final de `tests/test_main.py`:

```python
def test_las_filas_sin_radicado_se_avisan(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    wb = load_workbook(tmp_path / "x.xlsx")
    wb["GENERAL"].append([None])  # fila sin radicado pero ...
    wb["GENERAL"].cell(row=3, column=2, value="dato suelto")  # ... con datos en otra columna
    wb.save(tmp_path / "x.xlsx")
    avisos = []
    cfg = main_mod.cargar_config(args[args.index("--config") + 1])
    assert main_mod.ejecutar_ciclo(cfg, avisar_fn=avisos.append).codigo == 0
    assert any("sin radicado" in a for a in avisos)
```

- [ ] **Step 2: Ver que fallan**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_loader.py tests/test_main.py -q` → FAIL.

- [ ] **Step 3: Implementar `_radicados` y el conteo en `consultor/loader.py`**

Reemplazar `_radicados` por:

```python
def _radicados(valor) -> list[str]:
    """Radicados de una celda. El cuadro trae texto junto al número ("SEGUNDAINSTANCIA...")
    y a veces dos radicados pegados: se toma cada tramo de dígitos y se corta de a 23.

    Primero se busca en el texto tal cual, para que "…700-2026" no pegue el año al radicado;
    si no hay ninguno, se vuelve a buscar sin espacios, guiones ni puntos ("11001-40-03-…").
    Si no hay ninguno completo se devuelve el texto limpio, para que se vea como NO VERIFICADO.
    """
    if valor is None:
        return []
    if isinstance(valor, float):  # Excel guarda solo 15 cifras: el número ya está recortado
        return [f"numérico: {valor!r}"]
    texto = str(valor)
    limpio = re.sub(r"[\s\-\.]", "", texto)
    for fuente in (texto, limpio):
        encontrados = [
            tramo[i : i + 23]
            for tramo in re.findall(r"[0-9]+", fuente)
            if len(tramo) >= 23 and len(tramo) % 23 == 0
            for i in range(0, len(tramo), 23)
        ]
        if encontrados:
            return encontrados
    return [limpio] if limpio else []
```

En `cargar`, al inicio (antes de `wb = load_workbook`) poner `self.filas_sin_radicado = 0`, y reemplazar el comienzo del bucle por:

```python
            for fila in filas:
                # "ACTIVO" admite variantes del Excel como "ACTIVO -COBRO COSTAS"
                if self.estados and not celda(fila, i_est).lower().startswith(self.estados):
                    continue
                rads = _radicados(fila[i_rad]) if i_rad < len(fila) else []
                if not rads:
                    if any(_texto(c) for c in fila):
                        self.filas_sin_radicado += 1  # datos sin radicado: se avisa, no se pierde en silencio
                    continue
```

Y en `__init__` agregar `self.filas_sin_radicado = 0`.

- [ ] **Step 4: Avisar en `consultor/main.py`**

Reemplazar `radicados = crear_fuente(cfg["fuente"]).cargar()` por:

```python
            fuente = crear_fuente(cfg["fuente"])
            radicados = fuente.cargar()
            sin_radicado = getattr(fuente, "filas_sin_radicado", 0)
            if sin_radicado:
                aviso(
                    f"{sin_radicado} fila(s) del Excel tienen datos pero no tienen radicado "
                    "y no se consultan: revisar el cuadro."
                )
```

- [ ] **Step 5: Suite y commit**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q` → PASS.

```bash
git add consultor/loader.py consultor/main.py tests/test_loader.py tests/test_main.py
git commit -m "fix: el loader avisa las filas sin radicado y conserva radicados pegados a otros números"
```

---

### Task 6: `.gitignore` completo y `ejecutar_ciclo.bat` sin depender del PATH (hallazgos 6 y 8)

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/ejecutar_ciclo.bat`

- [ ] **Step 1: `.gitignore`**

Reemplazar su contenido por:

```
.venv/
__pycache__/
.pytest_cache/
datos/
reportes/
respaldo/
entrada/
config.toml
ajustes.json
estado.txt
cancelar.txt
*.xlsx
*.xls
*.xlsm
*.csv
*.pdf
*.db
*.db-journal
*.db.tmp
*.sqlite*
*.log
*.lock
vault/.obsidian/
```

- [ ] **Step 2: Verificar que ignora lo previsto**

Run:

```bash
git check-ignore -v consultor.db respaldo/consultor_2026-10-10.db ajustes.json avisos.log reporte_x.xlsx
```

Expected: cinco líneas, cada una con la regla que la ignora. Y `git status --short` no debe mostrar nada nuevo sin querer.

- [ ] **Step 3: `scripts/ejecutar_ciclo.bat`**

Reemplazar su contenido por (la documentación dice que la tarea corre oculta con `pythonw`; hoy el .bat llamaba al `python` del PATH):

```bat
@echo off
cd /d "%~dp0.."
if not exist reportes mkdir reportes
if not exist ".venv\Scripts\pythonw.exe" (
    echo %date% %time% Falta .venv\Scripts\pythonw.exe: no se ejecuto el ciclo. >> reportes\consola.log
    exit /b 2
)
start "" /wait ".venv\Scripts\pythonw.exe" -X utf8 -m consultor run --config config.toml
exit /b %ERRORLEVEL%
```

- [ ] **Step 4: Verificación manual (requiere la máquina de Luis, no se automatiza)**

1. Con el `.venv` real: doble clic en `scripts\ejecutar_ciclo.bat` con `--forzar` NO incluido. No debe abrirse ninguna consola; al terminar, `reportes\avisos.log` tiene la línea del ciclo (o el aviso del límite de 30 min).
2. `echo %ERRORLEVEL%` desde `cmd` tras ejecutarlo: 0 si el ciclo completó, 3 si lo rechazó el límite.
3. Renombrar `.venv` por un momento y repetir: debe dejar la línea "Falta .venv\Scripts\pythonw.exe" en `reportes\consola.log` y devolver 2. Volver a dejar `.venv` como estaba.

Si el código de salida de `start /wait` no llega bien en esa máquina, anotar el resultado aquí y dejar el .bat como estaba.

- [ ] **Step 5: Mover el reporte suelto (confirmar con Luis antes)**

`reporte_ciclo_0001_2026-10-09.xlsx` está en la raíz del repo (git lo ignora por `*.xlsx`, pero es información confidencial). Moverlo a `reportes\archivo\` solo con el visto bueno de Luis:

```bash
mkdir -p reportes/archivo && mv reporte_ciclo_0001_2026-10-09.xlsx reportes/archivo/
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore scripts/ejecutar_ciclo.bat
git commit -m "chore: gitignore completo para datos y ejecutar_ciclo.bat sin depender del PATH"
```

---

### Task 7: La ventana no se congela si algo falla al refrescar (hallazgo 10)

**Files:**
- Modify: `consultor/ventana.py` (`sondear`)
- Test: `tests/test_ventana.py`

- [ ] **Step 1: Prueba que falla**

```python
def test_si_refrescar_falla_la_ventana_lo_dice_y_sigue_sondeando(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    programados = []
    monkeypatch.setattr(v.raiz, "after", lambda ms, fn: programados.append(ms))

    def falla():
        raise RuntimeError("base dañada")

    monkeypatch.setattr(v, "refrescar", falla)
    v.sondear()
    assert "No se pudo actualizar" in v.etiqueta_estado.cget("text")
    assert programados == [1000]  # sigue sondeando
```

- [ ] **Step 2: Ver que falla**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_ventana.py -q` → FAIL (RuntimeError sin capturar).

- [ ] **Step 3: Implementar**

En `sondear`, reemplazar

```python
        self.refrescar()
        self.raiz.after(1000, self.sondear)
```

por

```python
        try:
            self.refrescar()
        except Exception as e:  # la pantalla debe seguir viva aunque la base o la carpeta fallen
            self.etiqueta_estado.config(
                text=f"No se pudo actualizar la pantalla ({type(e).__name__}). Avise a Sistemas.", fg=ROJO
            )
        finally:
            self.raiz.after(1000, self.sondear)
```

- [ ] **Step 4: Suite y commit**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q` → PASS.

```bash
git add consultor/ventana.py tests/test_ventana.py
git commit -m "fix: la ventana avisa y sigue sondeando si refrescar falla"
```

---

### Task 8: Un ciclo interrumpido no bloquea el siguiente por el límite de 30 minutos (hallazgo 13)

**Files:**
- Modify: `consultor/store.py` (`ultimo_cierre`)
- Test: `tests/test_store.py`

- [ ] **Step 1: Prueba que falla**

```python
def test_un_ciclo_interrumpido_no_cuenta_como_ultimo_cierre(store):
    c = store.iniciar_ciclo(AHORA)
    store.cerrar_ciclo(c, "Completo", AHORA)
    manana = AHORA + timedelta(days=1)
    store.iniciar_ciclo(AHORA - timedelta(hours=1))  # un ciclo del mismo día que quedó abierto
    store.cerrar_interrumpidos(manana)  # al día siguiente se marca Interrumpido con fin = manana
    assert store.ultimo_cierre() == AHORA
```

(`store.iniciar_ciclo(AHORA - 1h)` continúa el ciclo `c` si sigue abierto; como `c` ya está "Completo", crea uno nuevo, que es el que queda "En curso".)

- [ ] **Step 2: Ver que falla**

Run: `"$TEMP/venv/Scripts/python" -m pytest tests/test_store.py -q` → FAIL (devuelve `manana`).

- [ ] **Step 3: Implementar**

En `ultimo_cierre`, agregar a la consulta `AND estado NOT LIKE 'Interrumpido%'`:

```python
        f = self.con.execute("SELECT MAX(fin) AS fin FROM ciclo WHERE fin IS NOT NULL AND parcial = 0 "
            "AND estado NOT LIKE 'Cancelado%' AND estado NOT LIKE 'Interrumpido%'").fetchone()
```

- [ ] **Step 4: Suite y commit**

Run: `"$TEMP/venv/Scripts/python" -m pytest -q` → PASS.

```bash
git add consultor/store.py tests/test_store.py
git commit -m "fix: un ciclo interrumpido no cuenta para el límite entre ejecuciones"
```

---

### Task 9: Documentación al día

**Files:**
- Modify: `README.md`, `vault/Arquitectura.md`, `vault/00 Inicio.md`, `vault/Riesgos y pendientes.md`

- [ ] **Step 1: Corregir el carácter dañado del README**

La línea del campo de días en la sección Pantalla tiene un carácter de control (un `\a` mal escapado) donde debería decir `datos\ajustes.json`. Buscar con `grep -n "justes" README.md` y reescribir la línea con la ruta correcta:

```bash
python - <<'EOF'
import re
p = "README.md"
s = open(p, encoding="utf-8").read()
s = re.sub(r"queda en `datos[\x07]?justes\.json`", "queda en `datos\\\\ajustes.json`", s)
open(p, "w", encoding="utf-8").write(s)
EOF
grep -c $'\a' README.md
```

Expected: `0`.

- [ ] **Step 2: Alinear cifras y horarios**

- `vault/Arquitectura.md` y `vault/00 Inicio.md`: cambiar "141 pruebas" por el número real (`"$TEMP/venv/Scripts/python" -m pytest -q | tail -1`).
- Hora de la tarea programada: el README dice 06:30 y la bóveda 9:00. Preguntar a Luis cuál rige y dejar la misma en todos los lados.
- `vault/Riesgos y pendientes.md`: agregar los hallazgos que quedan abiertos (aviso activo y reintento tras bloqueo, dependencias con hashes, panel que abre la base cada segundo, rutas relativas, y el hallazgo 2 aceptado por Luis con su motivo).

- [ ] **Step 3: Commit**

```bash
git add README.md vault
git commit -m "docs: corregir el README, cifras y pendientes tras la auditoría"
```

---

## Self-Review

**Cobertura de la auditoría.** 1 → Task 1 (+ id entero en Task 2); 3 y 11 → Tasks 2 y 3; 4, 9 y 12 → Task 4; 5 → Task 5; 6 y 8 → Task 6; 10 → Task 7; 13 → Task 8; documentación → Task 9. Fuera a propósito: 2 (decisión de Luis), 7, 14, 15, 16 (listados arriba y anotados en `Riesgos y pendientes.md`).

**Placeholders.** Ninguno: cada paso trae el código y el comando. Las dos verificaciones manuales (Task 6 pasos 4 y 5) dependen de la máquina de Luis y lo dicen.

**Consistencia de nombres.** `ids_vistos` (Task 1, usado en `main.py`), `_entero` y `_fecha_iso` (Task 2), `_reciente` (Task 3), `MAX_BYTES_REPORTE` (Task 4, monkeypatch en la prueba), `filas_sin_radicado` (Task 5: atributo de `FuenteExcel` y `getattr` en `main.py`).

**Riesgos conocidos al ejecutar.**
- Task 2 puede romper fixtures de pruebas que no traigan `cant`: el paso 4 lo cubre.
- Task 4: si una prueba antigua inspecciona `avisos[-1]` o la lista completa de avisos, ahora hay un aviso más al principio; ajustar con `any(...)`.
- Task 5 reordena el filtro de estado antes de buscar el radicado: solo cambia el conteo de filas sin radicado, no qué radicados se consultan.
- Los radicados con referencia ya guardada (los 34 del viernes) no se reevalúan con la regla de "primera consulta"; eso se decide aparte.
