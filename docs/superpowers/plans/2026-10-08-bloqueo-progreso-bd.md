# Bloqueo, límite de ejecuciones, indicador de progreso y optimización de la base de datos

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. TDD: cada sección empieza con una prueba que falla.

Contexto: `2026-10-08-consultor-judicial.md` y `2026-10-08-correcciones-revision.md`. Comandos con `.venv\Scripts\python -m pytest`. Cada commit termina con `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"`. Sin rayas largas. No hacer peticiones al portal real en las pruebas.

Objetivo: que una persona no técnica no pueda lanzar dos ciclos a la vez ni repetir consultas sin querer, que vea que algo está pasando mientras corre, y que la base de datos no se degrade con el uso.

**Medición previa** (500 radicados, 40 actuaciones cada uno, 40 ciclos, `bench_bd.py` en el scratchpad de la sesión): 7 a 11 s de BD por ciclo; `tiene_referencia` hace `SCAN consulta`; `ultima_actuacion` usa `TEMP B-TREE`; las dos consultas de alertas hacen `SCAN a`; dos commits por radicado.

---

## A. Optimización de la base de datos

**Archivos:** `consultor/store.py`, `tests/test_store.py`

Cambios, todos idempotentes para que una base ya creada se migre al abrirla (`ESQUEMA` se ejecuta en cada arranque):
1. `CREATE INDEX IF NOT EXISTS ix_consulta_radicado ON consulta(radicado, estado)`.
2. `CREATE INDEX IF NOT EXISTS ix_actuacion_radicado_fecha ON actuacion(radicado, fecha_actuacion DESC, id_reg_actuacion DESC)` y `DROP INDEX IF EXISTS ix_actuacion_radicado` (el nuevo cubre `ids_conocidos` y evita el árbol temporal de `ultima_actuacion`).
3. `CREATE INDEX IF NOT EXISTS ix_alerta_ciclo ON alerta(ciclo_id)`.
4. `CREATE INDEX IF NOT EXISTS ix_alerta_pendiente ON alerta(id) WHERE estado = 'Pendiente'` para `PENDIENTES_SQL`, que tiene el literal `a.estado = 'Pendiente'`.
5. Método nuevo `registrar_radicados(self, radicados)`: un solo `executemany` en una sola transacción, con el mismo `INSERT ... ON CONFLICT DO UPDATE` que `registrar_radicado`. `registrar_radicado` se conserva (las pruebas lo usan).

- [ ] **Pruebas que fallan** (añadir a `tests/test_store.py`; `plan(store, sql, params)` es un ayudante local):
```python
def plan(store, sql, params=()):
    return " | ".join(f[3] for f in store.con.execute("EXPLAIN QUERY PLAN " + sql, params))


def test_tiene_referencia_usa_indice_y_no_recorre_la_tabla(store):
    p = plan(store, "SELECT 1 FROM consulta WHERE radicado = ? AND estado = 'Exitosa' LIMIT 1", (R.radicado,))
    assert "SCAN" not in p and "ix_consulta_radicado" in p


def test_ultima_actuacion_no_necesita_ordenar_aparte(store):
    p = plan(
        store,
        "SELECT fecha_actuacion, actuacion FROM actuacion WHERE radicado = ? "
        "ORDER BY fecha_actuacion DESC, id_reg_actuacion DESC LIMIT 1",
        (R.radicado,),
    )
    assert "TEMP B-TREE" not in p and "ix_actuacion_radicado_fecha" in p


def test_consultas_de_alertas_usan_indice(store):
    from consultor.store import ALERTAS_SQL, PENDIENTES_SQL

    assert "ix_alerta_ciclo" in plan(store, ALERTAS_SQL, (1,))
    assert "ix_alerta_pendiente" in plan(store, PENDIENTES_SQL, (1,))


def test_registrar_radicados_en_lote(store):
    otros = [Radicado(f"{i:023d}", empresa="X") for i in range(1, 6)]
    store.registrar_radicados(otros)
    assert store.con.execute("SELECT COUNT(*) FROM radicado").fetchone()[0] == 6  # 5 + el del fixture
    store.registrar_radicados([Radicado(otros[0].radicado, empresa="Y")])
    assert store.con.execute("SELECT empresa FROM radicado WHERE radicado = ?", (otros[0].radicado,)).fetchone()[0] == "Y"


def test_una_base_con_el_esquema_viejo_se_migra_al_abrirla(tmp_path):
    import sqlite3

    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript(
        "CREATE TABLE actuacion (id_reg_actuacion INTEGER PRIMARY KEY, radicado TEXT NOT NULL, "
        "fecha_actuacion TEXT, actuacion TEXT, anotacion TEXT, fecha_registro TEXT, fecha_inicial TEXT, "
        "fecha_final TEXT, primera_vez_visto TEXT);"
        "CREATE INDEX ix_actuacion_radicado ON actuacion(radicado);"
    )
    con.close()
    s = Store(ruta)
    nombres = {r[0] for r in s.con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert "ix_actuacion_radicado_fecha" in nombres
    assert "ix_actuacion_radicado" not in nombres
```
La prueba de migración puede requerir adaptar `ESQUEMA` para que `CREATE INDEX` de tablas que ya existen con otra forma no falle; mantener la compatibilidad con la base vieja es obligatorio.
- [ ] **Si el planificador no elige `ix_alerta_pendiente`** en `PENDIENTES_SQL`, no quitar la prueba en silencio: reportar el plan real y proponer la alternativa mínima (por ejemplo índice normal `alerta(estado, ciclo_id)`).
- [ ] **Implementar** los cinco cambios. En `consultor/main.py`, reemplazar el `store.registrar_radicado(r)` dentro del bucle por una sola llamada `store.registrar_radicados(radicados)` antes del bucle.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `perf: índices y lote de radicados para que la base no se degrade con el uso`

---

## B. Columna `parcial` en los ciclos y consulta del último cierre

Un ciclo con `--solo-radicado` no debe contar para el límite entre ejecuciones ni reanudarse como si fuera uno completo.

**Archivos:** `consultor/store.py`, `tests/test_store.py`

- [ ] **Pruebas que fallan:**
```python
def test_ultimo_cierre_ignora_ciclos_parciales_y_abiertos(store):
    assert store.ultimo_cierre() is None
    parcial = store.iniciar_ciclo(AHORA, parcial=True)
    store.cerrar_ciclo(parcial, "Completo", AHORA + timedelta(minutes=1))
    assert store.ultimo_cierre() is None
    completo = store.iniciar_ciclo(AHORA)
    assert store.ultimo_cierre() is None  # sigue En curso
    store.cerrar_ciclo(completo, "Completo", AHORA + timedelta(minutes=5))
    assert store.ultimo_cierre() == AHORA + timedelta(minutes=5)


def test_un_ciclo_parcial_abierto_no_se_reanuda_como_completo(store):
    parcial = store.iniciar_ciclo(AHORA, parcial=True)
    assert store.iniciar_ciclo(AHORA) != parcial
    assert store.iniciar_ciclo(AHORA, parcial=True) == parcial


def test_base_sin_columna_parcial_se_migra(tmp_path):
    import sqlite3

    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("CREATE TABLE ciclo (id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT NOT NULL, fin TEXT, estado TEXT NOT NULL);")
    con.execute("INSERT INTO ciclo (inicio, fin, estado) VALUES ('2026-10-01T07:00:00', '2026-10-01T07:05:00', 'Completo')")
    con.commit()
    con.close()
    s = Store(ruta)
    assert s.ultimo_cierre() == datetime(2026, 10, 1, 7, 5, 0)
```
- [ ] **Implementar:** columna `parcial INTEGER NOT NULL DEFAULT 0` en `ciclo`; en `Store.__init__`, tras `executescript(ESQUEMA)`, migrar: si `parcial` no está en `PRAGMA table_info(ciclo)`, `ALTER TABLE ciclo ADD COLUMN parcial INTEGER NOT NULL DEFAULT 0`. `iniciar_ciclo(self, ahora, parcial=False)` filtra y crea con `parcial = int(parcial)` (la búsqueda del ciclo abierto del día añade `AND parcial = ?`). `cerrar_interrumpidos` no cambia. Método nuevo:
```python
    def ultimo_cierre(self) -> datetime | None:
        f = self.con.execute("SELECT MAX(fin) AS fin FROM ciclo WHERE fin IS NOT NULL AND parcial = 0").fetchone()
        return datetime.fromisoformat(f["fin"]) if f["fin"] else None
```
(`ESQUEMA` define `ciclo` con la columna nueva para bases nuevas.)
- [ ] Commit: `feat: ciclos parciales y consulta del último cierre`

---

## C. Candado para que no corran dos ciclos a la vez

El candado lo da el sistema operativo sobre un archivo: si el programa muere, se libera solo, sin archivos huérfanos que limpiar. No usar `os.kill(pid, 0)` (en Windows termina procesos).

**Archivos:** `consultor/bloqueo.py` (nuevo), `tests/test_bloqueo.py` (nuevo)

- [ ] **Pruebas que fallan** (`tests/test_bloqueo.py`):
```python
import subprocess
import sys

import pytest

from consultor.bloqueo import Bloqueo, CicloEnCurso


def test_el_segundo_bloqueo_falla_y_muestra_el_estado(tmp_path):
    with Bloqueo(tmp_path) as b:
        b.publicar("06:30 | 12 de 44")
        with pytest.raises(CicloEnCurso) as e:
            with Bloqueo(tmp_path):
                pass
        assert "12 de 44" in e.value.estado


def test_se_libera_al_salir(tmp_path):
    with Bloqueo(tmp_path):
        pass
    with Bloqueo(tmp_path):  # no lanza
        pass
    assert not (tmp_path / "estado.txt").exists()


def test_se_libera_si_el_proceso_muere(tmp_path):
    codigo = (
        "import sys, time\n"
        "from consultor.bloqueo import Bloqueo\n"
        f"b = Bloqueo(r'{tmp_path}').__enter__()\n"
        "print('listo', flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "listo"
        with pytest.raises(CicloEnCurso):
            with Bloqueo(tmp_path):
                pass
    finally:
        proc.kill()
        proc.wait()
    with Bloqueo(tmp_path):  # el sistema operativo liberó el candado
        pass
```
- [ ] **Implementar** `consultor/bloqueo.py`:
```python
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import msvcrt

    def _bloquear(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _liberar(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _bloquear(fd):
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _liberar(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)


class CicloEnCurso(Exception):
    """Ya hay otro ciclo corriendo. estado trae su avance, si lo publicó."""

    def __init__(self, estado=""):
        super().__init__(estado)
        self.estado = estado


class Bloqueo:
    def __init__(self, carpeta):
        carpeta = Path(carpeta)
        self.ruta = carpeta / "consultor.lock"
        self.ruta_estado = carpeta / "estado.txt"
        self.fd = None

    def __enter__(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.ruta, os.O_RDWR | os.O_CREAT)
        try:
            _bloquear(self.fd)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise CicloEnCurso(self.leer_estado()) from None
        return self

    def __exit__(self, *exc):
        try:
            self.ruta_estado.unlink(missing_ok=True)
        finally:
            _liberar(self.fd)
            os.close(self.fd)
            self.fd = None

    def publicar(self, texto: str) -> None:
        """Deja el avance en un archivo que otro intento de ejecución puede leer."""
        tmp = self.ruta_estado.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, self.ruta_estado)

    def leer_estado(self) -> str:
        try:
            return self.ruta_estado.read_text(encoding="utf-8")
        except OSError:
            return ""
```
- [ ] Commit: `feat: candado del sistema operativo contra dos ciclos simultáneos`

---

## D. Indicador de progreso

**Archivos:** `consultor/main.py`, `consultor/consola.py` (nuevo), `tests/test_main.py`, `tests/test_consola.py` (nuevo)

- [ ] **Pruebas que fallan.** `tests/test_consola.py`:
```python
from consultor.consola import barra


def test_barra_vacia_a_medias_y_llena():
    assert barra(0, 10, ancho=10) == "[----------] 0/10"
    assert barra(5, 10, ancho=10) == "[#####-----] 5/10"
    assert barra(10, 10, ancho=10) == "[##########] 10/10"


def test_barra_con_total_cero_no_divide_por_cero():
    assert barra(0, 0, ancho=4) == "[####] 0/0"
```
En `tests/test_main.py`, ayudante `correr` acepta `progreso=None` y lo pasa a `correr_ciclo`:
```python
def test_el_progreso_se_informa_por_cada_radicado(tmp_path):
    rs = [Radicado(f"{i:023d}") for i in range(1, 4)]
    f = FetcherFalso({r.radicado: ok(act(1)) for r in rs})
    visto = []
    correr(tmp_path, rs, f, Store(":memory:"), Reloj(), progreso=lambda hecho, total, rad: visto.append((hecho, total, rad)))
    assert visto == [(1, 3, rs[0].radicado), (2, 3, rs[1].radicado), (3, 3, rs[2].radicado)]
```
- [ ] **Implementar.** `consultor/consola.py`:
```python
def barra(hecho: int, total: int, ancho: int = 30) -> str:
    lleno = ancho if total == 0 else int(ancho * hecho / total)
    return f"[{'#' * lleno}{'-' * (ancho - lleno)}] {hecho}/{total}"
```
`correr_ciclo` recibe `progreso=None` como último parámetro y, al final de **cada** iteración del bucle (también las de `continue` por radicado ya consultado o por ciclo detenido), llama `progreso(i + 1, len(radicados), r.radicado)` si no es `None`. Reestructurar el bucle con un `try/finally` por iteración o duplicar la llamada, lo que sea más simple, pero sin llamarla dos veces por radicado.
- [ ] Commit: `feat: informar el avance de cada radicado`

---

## E. Límite entre ejecuciones, candado y progreso en la línea de comandos

**Archivos:** `consultor/main.py`, `config.example.toml`, `tests/test_main.py`

Comportamiento de `ejecutar`:
1. Argumentos nuevos: `--forzar` (salta el límite entre ejecuciones, no el candado) y `--abrir` (abre el Excel al terminar, solo si existe `os.startfile`).
2. Config nueva, opcional: `[ejecucion] min_minutos_entre_ciclos = 30` (por defecto 30 si falta la sección).
3. Orden: leer config, **tomar el candado** sobre la carpeta de la base de datos (`Path(cfg["salida"]["base_datos"]).parent`), abrir el `Store`, comprobar el límite, cargar radicados, correr.
4. Si el candado está tomado: imprimir `Ya hay una consulta en curso (<estado>). No hace falta lanzarla otra vez: espera a que termine.` (sin el paréntesis si el estado viene vacío), registrar el intento en `avisos.log` y devolver **3**.
5. Si no es `--forzar` ni `--solo-radicado` y `ultimo_cierre()` es más reciente que el mínimo: imprimir `La última consulta terminó hace N min (a las HH:MM). Para no repetir consultas al portal, espera hasta las HH:MM, o pide a quien administra la herramienta que use --forzar.`, registrarlo en `avisos.log` y devolver **3**.
6. `--solo-radicado` crea el ciclo con `parcial=True`: `correr_ciclo` recibe `parcial` (nuevo parámetro con valor por defecto `False`) y lo pasa a `store.iniciar_ciclo`.
7. Progreso: si `sys.stdout.isatty()`, imprimir una cabecera `Consultando N procesos en la Rama Judicial. No cierres esta ventana.`, y por cada radicado reescribir la línea con `"\r" + barra(...)` y el radicado actual; al terminar, un salto de línea. Siempre (haya o no consola) llamar `bloqueo.publicar(f"{hora} | {hecho} de {total}")`. Los avisos que se impriman durante el ciclo deben empezar en línea nueva si la barra está activa.
8. Códigos de salida: 0 completo, 1 detenido o con fallas, 2 error inesperado, **3 no se ejecutó por candado o límite**.

- [ ] **Pruebas que fallan.** Un ayudante que escribe un Excel y un `config.toml` temporales y sustituye `consultor.main.Fetcher` por una clase falsa con `consultar` y `pausar`:
```python
import consultor.main as main_mod
from consultor.bloqueo import Bloqueo
from openpyxl import Workbook


def preparar(tmp_path, monkeypatch, minutos=30):
    wb = Workbook()
    ws = wb.active
    ws.title = "GENERAL"
    ws.append(["Radicado"])
    ws.append([R1.radicado])
    wb.save(tmp_path / "x.xlsx")
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'[fuente]\ntipo = "excel"\nruta = "{(tmp_path / "x.xlsx").as_posix()}"\nhoja = "GENERAL"\ncol_radicado = "Radicado"\n'
        f'[salida]\nbase_datos = "{(tmp_path / "datos" / "c.db").as_posix()}"\n'
        f'carpeta_reportes = "{(tmp_path / "reportes").as_posix()}"\nvalidador = "Alisson"\n'
        '[portal]\npausa_segundos = 0\nreintentos = 1\nespera_segundos = 0\ntimeout_segundos = 5\nmax_fallas_ciclo = 0.5\n'
        f'[ejecucion]\nmin_minutos_entre_ciclos = {minutos}\n',
        encoding="utf-8",
    )

    class Falso:
        def __init__(self, **k):
            pass

        def consultar(self, r):
            return ok(act(1))

        def pausar(self):
            pass

    monkeypatch.setattr(main_mod, "Fetcher", Falso)
    return ["run", "--config", str(cfg)]


def test_un_segundo_intento_seguido_es_rechazado_con_mensaje_claro(tmp_path, monkeypatch, capsys):
    args = preparar(tmp_path, monkeypatch)
    assert main_mod.ejecutar(args) == 0
    assert main_mod.ejecutar(args) == 3
    assert "espera hasta las" in capsys.readouterr().out


def test_forzar_salta_el_limite(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    assert main_mod.ejecutar(args) == 0
    assert main_mod.ejecutar(args + ["--forzar"]) == 0


def test_con_limite_en_cero_no_rechaza(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch, minutos=0)
    assert main_mod.ejecutar(args) == 0
    assert main_mod.ejecutar(args) == 0


def test_si_hay_otro_ciclo_corriendo_se_rechaza_y_dice_su_avance(tmp_path, monkeypatch, capsys):
    args = preparar(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("06:30 | 12 de 44")
        assert main_mod.ejecutar(args) == 3
    assert "12 de 44" in capsys.readouterr().out


def test_solo_radicado_no_cuenta_para_el_limite(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    assert main_mod.ejecutar(args + ["--solo-radicado", R1.radicado]) == 0
    assert main_mod.ejecutar(args) == 0  # no fue rechazado
```
- [ ] **Implementar** según el comportamiento de arriba. Añadir a `config.example.toml`:
```toml
[ejecucion]
min_minutos_entre_ciclos = 30
```
Reloj: usar `datetime.now()` para comparar con `ultimo_cierre()`; para el mensaje, calcular `hasta = ultimo + timedelta(minutes=minimo)`.
- [ ] `python -m pytest -q` completo en verde.
- [ ] Commit: `feat: candado, límite entre ejecuciones y barra de progreso en la línea de comandos`

---

## F. Script para personas no técnicas

**Archivos:** `scripts/ejecutar_ahora.bat` (nuevo), `README.md`, `scripts/ejecutar_ciclo.bat` (sin cambios)

- [ ] Crear `scripts/ejecutar_ahora.bat`:
```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -X utf8 -m consultor run --config config.toml --abrir
echo.
if %ERRORLEVEL% EQU 0 (echo Listo. El reporte se abrio en Excel.) else (echo La consulta no se ejecuto o termino con avisos. Lea el mensaje de arriba.)
echo.
pause
```
- [ ] README: reemplazar en "Limitaciones conocidas" la línea de "No se deben lanzar dos ciclos a la vez" (ahora lo impide el candado) y añadir una sección "Ejecutar a mano" que explique: doble clic en `scripts\ejecutar_ahora.bat`, que se ve una barra de avance, que si ya hay una consulta en curso o se consultó hace menos de 30 minutos el programa lo dice y no hace nada, y cómo cambiar el límite en `config.toml` (`min_minutos_entre_ciclos`). Mencionar el código de salida 3.
- [ ] Commit: `feat: script ejecutar_ahora.bat para quien no usa la terminal`

---

## Cierre

- [ ] `python -m pytest -q` completo en verde; reportar el conteo.
- [ ] Reportar sin ejecutar nada más: lista de commits y cualquier desviación respecto a este documento.
