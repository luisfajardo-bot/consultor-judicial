# Pantalla mínima con tkinter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. TDD: cada sección empieza con una prueba que falla.

Contexto: `2026-10-08-bloqueo-progreso-bd.md`. Comandos con `.venv\Scripts\python -m pytest`. Cada commit termina con `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Sin rayas largas. No hacer peticiones al portal real en las pruebas.

**Alcance decidido por el usuario:** ventana mínima. La lista de novedades en pantalla, la validación desde la ventana y cualquier ampliación quedan para después, y la decisión es de otra gerencia. Por eso la arquitectura separa la **lógica** (`panel.py`, sin tkinter) de la **vista** (`ventana.py`): una vista nueva, o una web futura, reutiliza la lógica sin tocarla.

**La ventana muestra:** una barra de progreso con el radicado hecho de total, el aviso de que el portal puede estar pidiendo esperar, el resumen de la última consulta, el botón **Consultar ahora** y el botón **Abrir último reporte**. No envía datos a ningún servicio externo.

**Fuente única del avance:** el archivo `estado.txt` que el ciclo ya publica en la carpeta de la base de datos (formato `HH:MM | N de M`). Así la ventana muestra el avance de cualquier ciclo, también el de la tarea programada, no solo el que ella lanza.

---

## A. Dos consultas nuevas en el store

**Archivos:** `consultor/store.py`, `tests/test_store.py`

- [ ] **Pruebas que fallan:**
```python
def test_ultimo_ciclo_devuelve_el_ultimo_cerrado(store):
    assert store.ultimo_ciclo() is None
    abierto = store.iniciar_ciclo(AHORA)
    assert store.ultimo_ciclo() is None  # sigue En curso
    store.cerrar_ciclo(abierto, "Completo", AHORA + timedelta(minutes=3))
    u = store.ultimo_ciclo()
    assert u["id"] == abierto
    assert u["estado"] == "Completo"
    assert u["fin"] == AHORA + timedelta(minutes=3)
    assert u["parcial"] is False


def test_contar_pendientes_cuenta_solo_las_pendientes(store):
    assert store.contar_pendientes() == 0
    c2 = _con_novedad(store)
    assert store.contar_pendientes() == 1
    alerta_id = store.filas_reporte(c2)[0]["alerta_id"]
    store.registrar_decision(alerta_id, DESCARTADA, "Alisson", AHORA)
    assert store.contar_pendientes() == 0
```
- [ ] **Implementar** en `Store`:
```python
    def ultimo_ciclo(self) -> dict | None:
        f = self.con.execute(
            "SELECT id, inicio, fin, estado, parcial FROM ciclo "
            "WHERE fin IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if f is None:
            return None
        return {
            "id": f["id"],
            "inicio": datetime.fromisoformat(f["inicio"]),
            "fin": datetime.fromisoformat(f["fin"]),
            "estado": f["estado"],
            "parcial": bool(f["parcial"]),
        }

    def contar_pendientes(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM alerta WHERE estado = 'Pendiente'").fetchone()[0]
```
- [ ] Commit: `feat: consultas del último ciclo y de alertas pendientes para el panel`

---

## B. Lógica del panel sin tkinter

**Archivos:** `consultor/panel.py` (nuevo), `tests/test_panel.py` (nuevo)

- [ ] **Pruebas que fallan** (`tests/test_panel.py`):
```python
import os
import time
from datetime import datetime, timedelta

from consultor.models import SIN_CAMBIO, Radicado, Veredicto
from consultor.panel import (
    leer_avance,
    resumen_ultimo_ciclo,
    texto_avance,
    texto_resumen,
    ultimo_reporte,
)
from consultor.store import Store
from tests.utiles import act, ok

AHORA = datetime(2026, 10, 12, 9, 0, 0)


def test_leer_avance_sin_archivo_es_none(tmp_path):
    assert leer_avance(tmp_path) is None


def test_leer_avance_interpreta_el_estado_y_los_segundos_sin_avance(tmp_path):
    ruta = tmp_path / "estado.txt"
    ruta.write_text("09:00 | 12 de 44", encoding="utf-8")
    ahora = ruta.stat().st_mtime + 150
    a = leer_avance(tmp_path, ahora=ahora)
    assert (a.hecho, a.total, a.hora_inicio) == (12, 44, "09:00")
    assert round(a.segundos_sin_avance) == 150


def test_leer_avance_con_texto_ilegible_es_none(tmp_path):
    (tmp_path / "estado.txt").write_text("basura", encoding="utf-8")
    assert leer_avance(tmp_path) is None


def test_ultimo_reporte_elige_el_de_mayor_numero_e_ignora_temporales(tmp_path):
    assert ultimo_reporte(tmp_path) is None
    for nombre in ["reporte_ciclo_0001_2026-10-09.xlsx", "reporte_ciclo_0010_2026-10-14.xlsx",
                   "reporte_ciclo_0002_2026-10-12.xlsx", "~$reporte_ciclo_0011_2026-10-16.xlsx"]:
        (tmp_path / nombre).write_bytes(b"x")
    assert ultimo_reporte(tmp_path).name == "reporte_ciclo_0010_2026-10-14.xlsx"


def _con_un_ciclo(estado="Completo"):
    store = Store(":memory:")
    r = Radicado("11001400307720210114700")
    store.registrar_radicados([r])
    c = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c, r.radicado, ok(act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    store.cerrar_ciclo(c, estado, AHORA + timedelta(minutes=2))
    return store


def test_resumen_del_ultimo_ciclo():
    assert resumen_ultimo_ciclo(Store(":memory:")) is None
    r = resumen_ultimo_ciclo(_con_un_ciclo())
    assert (r.total, r.exitosas, r.fallidas, r.novedades, r.pendientes_validar) == (1, 1, 0, 0, 0)
    assert r.estado == "Completo"


def test_textos_para_la_ventana():
    assert "Todavía no se ha hecho ninguna consulta" in texto_resumen(None)
    t = texto_resumen(resumen_ultimo_ciclo(_con_un_ciclo()))
    assert "2026-10-12 09:02" in t and "1 consultados" in t and "0 posibles novedades" in t
    assert "Consultando" in texto_avance(leer_avance_falso(5, 44, 10))
    assert "sin avance" in texto_avance(leer_avance_falso(5, 44, 200)).lower()
```
con el ayudante `leer_avance_falso(hecho, total, segundos)` definido en el mismo archivo y que construye un `Avance`.
- [ ] **Implementar** `consultor/panel.py`: dataclasses congeladas `Avance(hecho, total, segundos_sin_avance, hora_inicio)` y `ResumenCiclo(id, fin, estado, total, exitosas, fallidas, novedades, pendientes_validar)`; funciones `leer_avance(carpeta_datos, ahora=None)`, `resumen_ultimo_ciclo(store)`, `ultimo_reporte(carpeta)` (ordena por nombre, ignora los que empiezan por `~$`), `texto_resumen(resumen)` y `texto_avance(avance)`.
  - `texto_resumen(None)` devuelve `"Todavía no se ha hecho ninguna consulta."`.
  - `texto_resumen(r)` devuelve dos líneas: `Última consulta: AAAA-MM-DD HH:MM (estado)` y `N consultados, E exitosos, F sin verificar, V posibles novedades, P alertas por validar`.
  - `texto_avance(a)` devuelve `Consultando: H de T (desde las HH:MM)`; si `segundos_sin_avance > 90` añade ` Sin avance hace M min: el portal puede estar pidiendo esperar.`
  - `leer_avance` usa la expresión `(\d{1,2}:\d{2})\s*\|\s*(\d+) de (\d+)`.
  - `panel.py` NO importa tkinter.
- [ ] Commit: `feat: lógica del panel separada de la vista`

---

## C. Extraer del comando una función reutilizable

La ventana debe poder lanzar un ciclo con las mismas reglas que la línea de comandos: candado, límite entre ejecuciones, avance publicado.

**Archivos:** `consultor/main.py`, `tests/test_main.py`

**Condición:** todas las pruebas existentes de `tests/test_main.py` pasan SIN modificarse (usan `main_mod.Fetcher` monkeypatcheado y `capsys`). Por eso la función nueva vive en `main.py`, no en un módulo nuevo.

- [ ] **Pruebas que fallan** (añadir a `tests/test_main.py`, usando los ayudantes `preparar` y `Falso` ya existentes):
```python
def test_ejecutar_ciclo_devuelve_el_resultado_sin_imprimir(tmp_path, monkeypatch, capsys):
    args = preparar(tmp_path, monkeypatch)
    cfg = main_mod.cargar_config(args[args.index("--config") + 1])
    e = main_mod.ejecutar_ciclo(cfg)
    assert e.codigo == 0
    assert e.resumen.total == 1
    assert capsys.readouterr().out == ""  # la función no imprime, devuelve


def test_ejecutar_ciclo_rechazado_por_el_limite_devuelve_codigo_3_y_mensaje(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    cfg = main_mod.cargar_config(args[args.index("--config") + 1])
    assert main_mod.ejecutar_ciclo(cfg).codigo == 0
    e = main_mod.ejecutar_ciclo(cfg)
    assert e.codigo == 3
    assert "espera hasta las" in e.mensaje
    assert e.resumen is None


def test_ejecutar_ciclo_rechazado_por_el_candado_dice_el_avance(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    cfg = main_mod.cargar_config(args[args.index("--config") + 1])
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        e = main_mod.ejecutar_ciclo(cfg)
    assert e.codigo == 3 and "12 de 44" in e.mensaje


def test_ejecutar_ciclo_publica_el_avance_en_estado_txt_mientras_corre(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    cfg = main_mod.cargar_config(args[args.index("--config") + 1])
    visto = []
    main_mod.ejecutar_ciclo(cfg, progreso=lambda h, t, r: visto.append(
        (tmp_path / "datos" / "estado.txt").read_text(encoding="utf-8")))
    assert visto and "1 de 1" in visto[0]
    assert not (tmp_path / "datos" / "estado.txt").exists()  # se borra al terminar
```
- [ ] **Implementar:** dataclass `Ejecucion(codigo: int, mensaje: str, resumen: Resumen | None)` en `main.py`, y la función pública
```python
def ejecutar_ciclo(cfg, *, forzar=False, solo_radicado=None, progreso=None, avisar_fn=None) -> Ejecucion
```
que contiene lo que hoy hace `ejecutar` después de cargar la configuración: tomar el candado, abrir el `Store`, comprobar el límite entre ejecuciones, cargar radicados, construir el `Fetcher`, correr el ciclo y capturar errores inesperados. Diferencias con hoy:
  - No imprime. Los mensajes de rechazo por candado y por límite van en `Ejecucion.mensaje` con el mismo texto de hoy; quien llama los muestra. Todos los rechazos se siguen registrando en `avisos.log`.
  - Publica el avance **siempre** (llamando a `bloqueo.publicar(f"{HH:MM} | {hecho} de {total}")` por cada radicado) además de llamar a `progreso(hecho, total, radicado)` si no es `None`. La hora es la del inicio del ciclo.
  - `avisar_fn` por defecto escribe en `avisos.log`; si se pasa uno, se llama además.
  - Códigos iguales a los de hoy: 0, 1, 2, 3.
  `ejecutar(argv)` queda como envoltorio: analiza argumentos, carga la configuración, construye el `progreso` de consola (la barra) y el `avisar_fn` que imprime, llama a `ejecutar_ciclo`, imprime `mensaje` si `codigo == 3` y devuelve el código. Debe seguir cumpliendo todas las pruebas existentes sin cambios.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `refactor: ejecutar_ciclo reutilizable por la línea de comandos y la ventana`

---

## D. La ventana

**Archivos:** `consultor/ventana.py` (nuevo), `consultor/main.py` (comando), `scripts/abrir_panel.bat` (nuevo), `tests/test_ventana.py` (nuevo)

Diseño de la vista, sin lógica de negocio (todo lo que decide está en `panel.py` y `main.py`):
- Clase `Ventana` con `__init__(self, raiz, cfg, ejecutar=ejecutar_ciclo)`; el parámetro `ejecutar` permite inyectar uno falso en pruebas.
- Widgets (tkinter y ttk, textos en español): título "Consultor Judicial"; etiqueta del resumen (`texto_resumen`); `ttk.Progressbar` determinada con una etiqueta debajo (`texto_avance`); un mensaje de estado; botones **Consultar ahora** y **Abrir último reporte**.
- Método `refrescar(self)`: lee `leer_avance(carpeta_datos)`. Si hay avance, muestra la barra (`maximum = total`, `value = hecho`), el texto y **deshabilita** "Consultar ahora" (otro ciclo corre, sea de la ventana o de la tarea programada). Si no hay avance, oculta o vacía la barra, habilita el botón y, solo en ese caso, abre un `Store` de vida corta para actualizar el resumen (`resumen_ultimo_ciclo`), capturando `sqlite3.OperationalError` (base ocupada) y dejando el texto anterior. Nunca abre el `Store` mientras haya un ciclo en curso.
- Botón **Consultar ahora:** lanza `ejecutar(cfg)` en un `threading.Thread` daemon, deshabilita el botón, y guarda el resultado en una `queue.Queue`. El resultado no toca widgets desde el hilo.
- Método `sondear(self)`: vacía la cola (si hay una `Ejecucion`, la muestra: si `codigo` es 3 o 2 o 1 pone el `mensaje` o un texto equivalente en la etiqueta de estado en rojo oscuro; si 0, "Consulta terminada" en verde oscuro), llama a `refrescar()` y se reprograma con `raiz.after(1000, self.sondear)`.
- Botón **Abrir último reporte:** `os.startfile(ultimo_reporte(carpeta_reportes))`; si no hay reporte, mensaje "Todavía no hay reportes."
- Accesibilidad: contraste suficiente, tamaño de letra de al menos 11 pt, botones alcanzables con Tab y activables con Enter o espacio, foco visible.
- Función `abrir(ruta_config) -> int`: carga la configuración, crea `tk.Tk()`, la `Ventana`, arranca `sondear()` y `mainloop()`. Devuelve 0.
- En `main.py`, el comando `ventana` (junto a `run`) llama a `abrir(args.config)` y devuelve su valor. Importar tkinter solo dentro de `ventana.py` y esa importación solo ocurre con el comando `ventana`, para no exigirlo en `run`.
- `scripts/abrir_panel.bat`:
```bat
@echo off
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" -X utf8 -m consultor ventana --config config.toml
```

- [ ] **Pruebas** (`tests/test_ventana.py`; saltar si no hay entorno gráfico):
```python
import tkinter as tk

import pytest

import consultor.main as main_mod
from consultor.bloqueo import Bloqueo
from consultor.ventana import Ventana
from tests.test_main import preparar


@pytest.fixture
def raiz():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("sin entorno gráfico")
    r.withdraw()
    yield r
    r.destroy()


def _cfg(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    return main_mod.cargar_config(args[args.index("--config") + 1])


def test_sin_consultas_previas_muestra_el_texto_inicial_y_habilita_el_boton(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.refrescar()
    assert "Todavía no se ha hecho ninguna consulta" in v.etiqueta_resumen.cget("text")
    assert str(v.boton_consultar.cget("state")) == "normal"


def test_con_otro_ciclo_corriendo_muestra_el_avance_y_deshabilita_el_boton(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg)
        v.refrescar()
        assert "12 de 44" in v.etiqueta_avance.cget("text")
        assert float(v.barra["value"]) == 12 and float(v.barra["maximum"]) == 44
        assert str(v.boton_consultar.cget("state")) == "disabled"


def test_consultar_ahora_corre_en_un_hilo_y_muestra_el_resultado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "terminada" in v.etiqueta_estado.cget("text").lower()
    assert "1 consultados" in v.etiqueta_resumen.cget("text")


def test_si_el_ciclo_es_rechazado_se_muestra_el_mensaje(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    main_mod.ejecutar_ciclo(cfg)  # deja un ciclo reciente: el siguiente será rechazado por el límite
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "espera hasta las" in v.etiqueta_estado.cget("text")
```
Nombres de atributos obligatorios para que las pruebas funcionen: `etiqueta_resumen`, `etiqueta_avance`, `etiqueta_estado`, `barra`, `boton_consultar`, `boton_reporte`, `hilo`. Si una prueba necesita un ajuste por un detalle de tkinter (por ejemplo `update()` antes de leer `cget`), hacerlo con el cambio mínimo y reportarlo.
- [ ] **Verificación manual** (sin prueba automática): lanzar `.venv\Scripts\python -X utf8 -m consultor ventana --config config.toml` durante unos segundos y comprobar que abre y que cierra sin error; capturar la salida de error si falla. NO pulsar "Consultar ahora" contra el portal real durante esta verificación.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `feat: pantalla mínima con tkinter para ver el avance y consultar`

---

## E. Documentación

- [ ] `README.md`: sección "Pantalla" que explique, para una persona no técnica: doble clic en `scripts\abrir_panel.bat`; qué muestra; que si hay otra consulta corriendo (por ejemplo la programada de las 9:00) el botón queda desactivado y se ve el avance; que "Sin avance hace N min" casi siempre es el portal pidiendo esperar y no hay que hacer nada; y que la ventana no envía datos a ningún sitio.
- [ ] Commit: `docs: la pantalla en el README`

## Cierre

- [ ] `python -m pytest -q` completo en verde; reportar el conteo.
- [ ] Reportar: lista de commits y cualquier desviación respecto a este documento.
