# Correcciones tras la revisión y la prueba de humo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. TDD: cada corrección empieza con una prueba que falla.

Origen: la prueba de humo contra el portal real (hallazgo A) y la revisión independiente del código (hallazgos B a H). Contexto y convenciones: `2026-10-08-consultor-judicial.md`. Comandos con `.venv\Scripts\python -m pytest`. Cada commit termina con `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Sin rayas largas.

**Fuera de alcance, queda documentado como riesgo:** decisión corregida en el Excel que se ignora porque solo se acepta la primera (revisión 9); dos ejecuciones simultáneas del mismo día (revisión 11).

---

## A. El portal rechaza el User-Agent por defecto de requests (HTTP 403)

Verificado: `python-requests/x` recibe 403; `curl`, un User-Agent vacío, uno de navegador y uno descriptivo reciben 200. Nos identificamos de forma honesta, sin imitar un navegador.

**Archivos:** `consultor/fetcher.py`, `tests/test_fetcher.py`

- [ ] **Prueba que falla** (añadir a `tests/test_fetcher.py`):
```python
from consultor.fetcher import USER_AGENT


def test_la_sesion_por_defecto_se_identifica_y_no_usa_el_user_agent_de_requests():
    f = Fetcher()
    assert f.sesion.headers["User-Agent"] == USER_AGENT
    assert not USER_AGENT.startswith("python-requests")
```
- [ ] **Implementación** en `consultor/fetcher.py`: constante `USER_AGENT = "ConsultorJudicial/1.0 (Gerencia Juridica; consulta de procesos propios)"` y, en `Fetcher.__init__`, reemplazar `self.sesion = sesion or requests.Session()` por:
```python
        if sesion is None:
            sesion = requests.Session()
            sesion.headers["User-Agent"] = USER_AGENT
        self.sesion = sesion
```
- [ ] Commit: `fix: identificarse con un User-Agent propio, el portal rechaza el de requests`

---

## B. Un carácter de control en un texto tumba el reporte y la novedad se pierde

Dos defectos: (1) `openpyxl` lanza `IllegalCharacterError` con caracteres de control (por ejemplo `\x0b` pegado desde Word); (2) `main` cierra el ciclo como Completo antes de escribir el reporte, así que un fallo del reporte deja las actuaciones como conocidas sin que nadie vea la alerta.

**Archivos:** `consultor/reporter.py`, `consultor/main.py`, `tests/test_reporter.py`, `tests/test_main.py`

- [ ] **Pruebas que fallan.** En `tests/test_reporter.py`:
```python
def test_caracteres_de_control_se_eliminan_en_vez_de_romper_el_reporte(tmp_path):
    wb = load_workbook(escribir(tmp_path, [novedad(anotacion="Auto que\x0bdecreta pruebas")]))
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    assert hoja.cell(row=2, column=enc.index("Anotación detectada") + 1).value == "Auto quedecreta pruebas"
```
En `tests/test_main.py` (añadir `import consultor.main as main_mod` arriba):
```python
def test_si_falla_el_reporte_el_ciclo_queda_abierto_y_se_reanuda_sin_reconsultar(tmp_path, monkeypatch):
    store, reloj = Store(":memory:"), Reloj()
    f = FetcherFalso({R1.radicado: ok(act(1))})
    correr(tmp_path, [R1], f, store, reloj)
    reloj.avanzar()
    f.respuestas = {R1.radicado: ok(act(2, texto="Auto"), act(1))}
    original = main_mod.escribir_reporte

    def falla(*a, **k):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(main_mod, "escribir_reporte", falla)
    with pytest.raises(RuntimeError):
        correr(tmp_path, [R1], f, store, reloj)
    monkeypatch.setattr(main_mod, "escribir_reporte", original)
    llamadas_antes = len(f.llamadas)
    res = correr(tmp_path, [R1], f, store, reloj)
    assert len(f.llamadas) == llamadas_antes  # no reconsulta
    assert res.novedades == 1
    enc, filas = hoja_alertas(res.reporte)
    assert filas[0][enc.index("Resultado")] == "POSIBLE NOVEDAD"
```
- [ ] **Implementación.**
  - `consultor/reporter.py`: `from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE` y en `_agregar`, antes de `hoja.append`, limpiar:
```python
    valores = [ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v for v in valores]
```
  - `consultor/main.py`: en `correr_ciclo`, escribir el reporte **antes** de `store.cerrar_ciclo`. Orden final: calcular `estado`, `res = store.resumen(ciclo_id)`, `ruta = escribir_reporte(...)`, luego `store.cerrar_ciclo(ciclo_id, estado, ahora())`, luego el aviso.
- [ ] Commit: `fix: limpiar caracteres de control y cerrar el ciclo solo tras escribir el reporte`

---

## C. Alertas pendientes de un ciclo que no llegó a reporte desaparecen

Si un ciclo se interrumpe y no se reanuda el mismo día, queda "En curso" para siempre y sus alertas Pendiente no salen en ningún reporte. Dos cambios: los ciclos abiertos de días anteriores se marcan Interrumpido con aviso, y **todo reporte incluye las alertas Pendiente de otros ciclos**.

**Archivos:** `consultor/store.py`, `consultor/main.py`, `tests/test_store.py`, `tests/test_main.py`

- [ ] **Pruebas que fallan.** En `tests/test_store.py`:
```python
def test_alerta_pendiente_de_otro_ciclo_aparece_en_el_reporte_siguiente(store):
    c2 = _con_novedad(store)            # alerta Pendiente nacida en el ciclo 2
    store.cerrar_ciclo(c2, "Completo", AHORA)
    c3 = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c3, R.radicado, ok(act(2), act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    filas = store.filas_reporte(c3)
    pendientes = [f for f in filas if f["alerta_id"]]
    assert len(pendientes) == 1
    assert pendientes[0]["resultado"] == POSIBLE_NOVEDAD
    assert pendientes[0]["decision"] == PENDIENTE
    assert "ciclo" in pendientes[0]["motivo"]


def test_alerta_ya_decidida_no_reaparece(store):
    c2 = _con_novedad(store)
    alerta_id = store.filas_reporte(c2)[0]["alerta_id"]
    store.registrar_decision(alerta_id, DESCARTADA, "Alisson", AHORA)
    store.cerrar_ciclo(c2, "Completo", AHORA)
    c3 = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c3, R.radicado, ok(act(2), act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    assert [f for f in store.filas_reporte(c3) if f["alerta_id"]] == []


def test_ciclos_abiertos_de_dias_anteriores_se_marcan_interrumpidos(store):
    viejo = store.iniciar_ciclo(AHORA)
    manana = AHORA + timedelta(days=1)
    assert store.cerrar_interrumpidos(manana) == 1
    assert store.cerrar_interrumpidos(manana) == 0
    assert store.iniciar_ciclo(manana) != viejo
```
(añadir `from datetime import datetime, timedelta` en los imports de ese archivo). En `tests/test_main.py`:
```python
def test_ciclo_interrumpido_de_otro_dia_se_avisa_y_su_alerta_sigue_visible(tmp_path, monkeypatch):
    store, reloj, avisos = Store(":memory:"), Reloj(), []
    f = FetcherFalso({R1.radicado: ok(act(1))})
    correr(tmp_path, [R1], f, store, reloj, avisos)
    reloj.avanzar()
    f.respuestas = {R1.radicado: ok(act(2, texto="Auto"), act(1))}

    def falla(*a, **k):
        raise RuntimeError("se cayó la máquina")

    monkeypatch.undo()
    monkeypatch.setattr(main_mod, "escribir_reporte", falla)
    with pytest.raises(RuntimeError):
        correr(tmp_path, [R1], f, store, reloj, avisos)
    monkeypatch.undo()
    reloj.avanzar()
    res = correr(tmp_path, [R1], f, store, reloj, avisos)
    assert any("interrumpido" in a.lower() for a in avisos)
    enc, filas = hoja_alertas(res.reporte)
    assert [x[enc.index("Actuación detectada")] for x in filas] == ["Auto"]
```
- [ ] **Implementación.**
  - `store.py`, método nuevo:
```python
    def cerrar_interrumpidos(self, ahora: datetime) -> int:
        """Marca Interrumpido los ciclos abiertos de días anteriores."""
        with self.con:
            cur = self.con.execute(
                "UPDATE ciclo SET estado = 'Interrumpido', fin = ? "
                "WHERE estado = 'En curso' AND substr(inicio, 1, 10) <> ?",
                (_iso(ahora), ahora.date().isoformat()),
            )
        return cur.rowcount
```
  - `store.py`, constante `PENDIENTES_SQL` y su uso al final de `filas_reporte` (después del bucle de consultas):
```python
PENDIENTES_SQL = """
SELECT a.id, a.radicado, a.ciclo_id, a.anterior, a.estado,
       t.fecha_actuacion, t.actuacion, t.anotacion,
       r.empresa AS empresa,
       COALESCE(NULLIF(c.despacho, ''), r.despacho, '') AS despacho,
       c.hora AS hora
FROM alerta a
JOIN actuacion t ON t.id_reg_actuacion = a.id_reg_actuacion
JOIN radicado r ON r.radicado = a.radicado
LEFT JOIN consulta c ON c.ciclo_id = a.ciclo_id AND c.radicado = a.radicado
WHERE a.estado = 'Pendiente' AND a.ciclo_id <> ?
ORDER BY a.id
"""
```
    Cada fila de `PENDIENTES_SQL` se añade a `filas` con: `alerta_id=a["id"]`, `empresa`, `radicado`, `despacho`, `estado_consulta="Exitosa"`, `resultado=POSIBLE_NOVEDAD`, `anterior`, `fecha_detectada`, `detectada`, `anotacion`, `hora=a["hora"] or ""`, `motivo=f"alerta pendiente del ciclo {a['ciclo_id']}"`, `decision=a["estado"]`, `validada_por=""`, `validada_en=""`.
  - `main.py`, en `correr_ciclo`, justo antes de `ciclo_id = store.iniciar_ciclo(ahora())`:
```python
    interrumpidos = store.cerrar_interrumpidos(ahora())
    if interrumpidos:
        avisar_fn(f"{interrumpidos} ciclo(s) anterior(es) quedaron interrumpido(s). Sus alertas pendientes siguen en el reporte.")
```
- [ ] Commit: `fix: las alertas pendientes de ciclos anteriores siguen apareciendo en el reporte`

---

## D. El fetcher ignora procesos adicionales, páginas adicionales y trata un 404 inesperado como éxito

Tres defectos en `consultor/fetcher.py`:
1. Solo se usa `procesos[0]`; un radicado puede devolver varios procesos (por ejemplo tras remisión a otro despacho).
2. Solo se pide `pagina=1` aunque haya más. Cada actuación trae el campo `cant` con el total del proceso.
3. Un 404 en actuaciones se toma como "sin actuaciones" siempre. Solo lo es si el cuerpo trae `"Message": "No se encontraron Actuaciones ..."`. Cualquier otro 404 es una falla del portal.

**Archivos:** `consultor/fetcher.py`, `tests/test_fetcher.py`

- [ ] **Cambiar la prueba existente** `test_actuaciones_404_es_proceso_sin_actuaciones`: la respuesta falsa pasa a ser `RespuestaFalsa(404, {"StatusCode": 404, "Message": "No se encontraron Actuaciones para el Proceso: 108832900"})`. Mantener sus aserciones.
- [ ] **Pruebas nuevas que fallan** (`tests/test_fetcher.py`):
```python
def test_404_sin_el_mensaje_esperado_es_falla_del_portal():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, {"StatusCode": 404, "Message": "Otra cosa"})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def test_404_con_cuerpo_ilegible_es_falla_del_portal():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, json_invalido=True)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def _pagina(ids, cant):
    return RespuestaFalsa(
        200,
        {
            "actuaciones": [
                {
                    "idRegActuacion": i,
                    "fechaActuacion": "2026-05-15T00:00:00",
                    "actuacion": "x",
                    "cant": cant,
                }
                for i in ids
            ]
        },
    )


def test_pide_mas_paginas_hasta_completar_el_total():
    rutas = rutas_ok()
    rutas["Actuaciones"] = [_pagina([3, 2], cant=3), _pagina([1], cant=3)]
    f, sesion, _ = crear(rutas)
    c = f.consultar(RAD)
    assert [a.id_reg_actuacion for a in c.actuaciones] == [3, 2, 1]
    paginas = [p["pagina"] for u, p in sesion.llamadas if "Actuaciones" in u]
    assert paginas == [1, 2]


def test_varios_procesos_para_un_radicado_se_unen_sin_duplicar():
    rutas = rutas_ok()
    busqueda = {"procesos": [{"idProceso": 1, "despacho": "A"}, {"idProceso": 2, "despacho": "B"}]}
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, busqueda)
    rutas["Actuaciones"] = [_pagina([5, 4], cant=2), _pagina([4, 9], cant=2)]
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.id_proceso == 1 and c.despacho == "A"
    assert sorted(a.id_reg_actuacion for a in c.actuaciones) == [4, 5, 9]
```
- [ ] **Implementación** en `consultor/fetcher.py`:
  - Constante `MAX_PAGINAS = 20`.
  - `_get`: en la rama `status_code == 404`, devolver el cuerpo si es JSON: 
```python
                if resp.status_code == 404:
                    try:
                        return 404, resp.json()
                    except ValueError:
                        return 404, None
```
  - Función de módulo:
```python
def _sin_actuaciones(datos) -> bool:
    return isinstance(datos, dict) and "No se encontraron" in str(datos.get("Message", ""))
```
  - Método nuevo:
```python
    def _actuaciones(self, id_proceso, radicado) -> list[Actuacion]:
        acumuladas: list[Actuacion] = []
        pagina = 1
        while True:
            estado, datos = self._get(
                f"{BASE}/Proceso/Actuaciones/{id_proceso}", {"pagina": pagina}
            )
            if estado == 404:
                if pagina == 1 and not _sin_actuaciones(datos):
                    raise ErrorPortal("404 inesperado al pedir actuaciones")
                break
            lista = datos["actuaciones"]
            acumuladas.extend(_actuacion(a, radicado) for a in lista)
            total = max((a.get("cant") or 0 for a in lista), default=0)
            if not lista or len(acumuladas) >= total:
                break
            pagina += 1
            if pagina > MAX_PAGINAS:
                raise ErrorPortal(f"más de {MAX_PAGINAS} páginas de actuaciones")
        return acumuladas
```
  - `consultar`: después de comprobar `procesos`, reemplazar la toma de `procesos[0]` y la llamada a actuaciones por:
```python
            primero = procesos[0]
            id_proceso = primero["idProceso"]
            vistas: dict[int, Actuacion] = {}
            for p in procesos:
                for a in self._actuaciones(p["idProceso"], r.radicado):
                    vistas.setdefault(a.id_reg_actuacion, a)
            return Consulta(
                EXITOSA,
                id_proceso=id_proceso,
                despacho=(primero.get("despacho") or "").strip(),
                ultima_actualizacion=self._ultima_actualizacion(id_proceso),
                actuaciones=tuple(vistas.values()),
            )
```
- [ ] Commit: `fix: varios procesos por radicado, paginación completa y 404 inesperado como falla`

---

## E. El portal puede fallar de forma que R5 no lo detecta

(1) "Sin resultados" no cuenta para R5: si el portal responde 200 con `procesos: []` para todos, el ciclo cierra Completo. (2) R5 solo se evalúa desde 10 consultas: con menos, un portal caído deja el ciclo Completo con código 0.

**Archivos:** `consultor/fetcher.py`, `consultor/main.py`, `tests/test_fetcher.py`, `tests/test_main.py`

- [ ] **Cambiar la prueba** `test_busqueda_vacia_es_sin_resultados_y_no_es_falla_del_portal`: renombrar a `test_busqueda_vacia_es_sin_resultados_y_cuenta_para_r5` y afirmar `c.falla_portal is True` (el motivo sigue siendo `"sin resultados"`). `test_radicado_invalido_...` NO cambia: un radicado mal escrito no es falla del portal.
- [ ] **Prueba que falla** (`tests/test_main.py`):
```python
def test_portal_caido_con_pocos_radicados_no_cierra_como_completo(tmp_path):
    radicados = [Radicado(f"{i:023d}") for i in range(1, 4)]
    caida = Consulta(FALLIDA, motivo="HTTP 503", falla_portal=True)
    f = FetcherFalso({r.radicado: caida for r in radicados})
    avisos = []
    res = correr(tmp_path, radicados, f, Store(":memory:"), Reloj(), avisos)
    assert res.estado == "Completo con fallas de la fuente"
    assert any("Fuente no disponible" in a for a in avisos)
```
- [ ] **Implementación.**
  - `fetcher.py`: `return Consulta(FALLIDA, motivo="sin resultados", falla_portal=True)`. Actualizar el comentario de `Consulta.falla_portal` en `models.py`: "cuenta para R5 (el portal falló o no devolvió el proceso)".
  - `main.py`: tras el bucle, reemplazar el cálculo de `estado`:
```python
    fuente_caida = consultados > 0 and fallas / consultados > max_fallas
    if detenido:
        estado = "Detenido: fuente no disponible"
    elif fuente_caida:
        estado = "Completo con fallas de la fuente"
        avisar_fn(
            f"Fuente no disponible: fallaron {fallas} de {consultados} consultas. "
            "Activar consulta manual."
        )
    else:
        estado = "Completo"
```
- [ ] Commit: `fix: R5 cuenta sin resultados y se evalúa también al cerrar el ciclo`

---

## F. Una lista vacía de radicados cierra como Completo

**Archivos:** `consultor/main.py`, `tests/test_main.py`

- [ ] **Prueba que falla:**
```python
def test_lista_vacia_avisa_y_no_es_completo(tmp_path):
    avisos = []
    res = correr(tmp_path, [], FetcherFalso({}), Store(":memory:"), Reloj(), avisos)
    assert res.estado == "Lista vacía"
    assert res.reporte is None
    assert any("vacía" in a for a in avisos)
```
- [ ] **Implementación:** `Resumen.reporte` pasa a `Path | None`. Al inicio de `correr_ciclo` (antes de importar decisiones):
```python
    if not radicados:
        avisar_fn(
            "La lista de radicados está vacía. No se consultó nada: "
            "revisar la fuente y los filtros de estado."
        )
        return Resumen(0, 0, 0, 0, 0, "Lista vacía", None)
```
`ejecutar` ya devuelve 1 para cualquier estado distinto de "Completo".
- [ ] Commit: `fix: avisar cuando la lista de radicados llega vacía`

---

## G. Una celda mala en la columna "ID alerta" descarta todas las decisiones del archivo

**Archivos:** `consultor/reporter.py`, `tests/test_reporter.py`

- [ ] **Prueba que falla:**
```python
def test_id_de_alerta_invalido_se_avisa_y_no_descarta_las_demas_decisiones(tmp_path):
    ruta = escribir(tmp_path, [novedad(alerta_id=7), novedad(alerta_id=8)])
    wb = load_workbook(ruta)
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    for fila, decision in ((2, "Confirmada"), (3, "Descartada")):
        hoja.cell(row=fila, column=enc.index("Decisión") + 1, value=decision)
        hoja.cell(row=fila, column=enc.index("Validó") + 1, value="Alisson Rengifo")
    hoja.cell(row=2, column=enc.index("ID alerta") + 1, value="nota")
    wb.save(ruta)
    avisos = []
    assert leer_decisiones(tmp_path, avisos.append) == [(8, "Descartada", "Alisson Rengifo")]
    assert any("ID de alerta" in a for a in avisos)
```
- [ ] **Implementación** en `leer_decisiones`, dentro del bucle de filas:
```python
                for f in filas:
                    if not (f[i_id] and f[i_dec] in (CONFIRMADA, DESCARTADA)):
                        continue
                    try:
                        alerta_id = int(f[i_id])
                    except (TypeError, ValueError):
                        if avisar_fn:
                            avisar_fn(f"ID de alerta inválido ({f[i_id]!r}) en {ruta.name}; fila ignorada.")
                        continue
                    decisiones.append((alerta_id, f[i_dec], f[i_val] or ""))
```
- [ ] Commit: `fix: una fila con ID de alerta inválido no descarta el resto de decisiones`

---

## H. La consola en cp1252 puede romper el manejador de errores

Al redirigir la salida a `consola.log`, `print` usa cp1252 y un texto fuera de ese juego lanza `UnicodeEncodeError` dentro del manejador de errores.

**Archivos:** `consultor/__main__.py`

- [ ] **Implementación** (sin prueba automática; se verifica a mano):
```python
import sys

from .main import ejecutar

if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None:
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(ejecutar(sys.argv[1:]))
```
- [ ] **Verificación manual:** `.venv\Scripts\python -m consultor run --solo-radicado 123 --config config.toml > salida.txt` no lanza error y `salida.txt` se lee bien en UTF-8. (Requiere `config.toml`, que ya existe localmente; borrar `salida.txt` después.)
- [ ] Commit: `fix: salida estándar en UTF-8 para no romper con redirección`

---

## Cierre

- [ ] `python -m pytest -q` en verde (esperado: 46 + las pruebas nuevas, menos ninguna).
- [ ] Documentar en `README.md`, sección nueva "Limitaciones conocidas": (1) una decisión corregida en el Excel se ignora, solo cuenta la primera, y (2) no se deben lanzar dos ciclos a la vez.
- [ ] Commit: `docs: limitaciones conocidas`
