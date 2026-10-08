# Consultor Judicial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Herramienta de línea de comandos que consulta radicados en la API de la Rama Judicial, detecta actuaciones nuevas y genera un Excel de alertas que valida Alisson Rengifo.

**Architecture:** Pipeline lineal en un paquete Python `consultor/`: `loader` (fuente intercambiable), `fetcher` (3 GET por radicado), `comparator` (lógica pura), `store` (SQLite, única fuente de verdad), `reporter` (Excel) y `main` (orquesta un ciclo). Diseño completo en `docs/superpowers/specs/2026-10-07-consultor-judicial-design.md`.

**Tech Stack:** Python 3.11 o superior, `requests`, `openpyxl`, `sqlite3` y `tomllib` de la biblioteca estándar, `pytest`.

**Convenciones:**
- Todos los comandos se ejecutan en la raíz `C:\Users\luis.fajardo\Desktop\consultor_judicial` con el entorno virtual activo (`.venv\Scripts\activate`).
- Cada commit lleva la línea `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` como segundo `-m`.
- Sin rayas largas en textos y sin muletillas de marketing (antislop, modo durante).

**Datos verificados de la API** (2026-10-08, solo lectura):
- Búsqueda: `GET {BASE}/Procesos/Consulta/NumeroRadicacion?numero=<23 dígitos>&SoloActivos=false&pagina=1` devuelve `{"procesos":[{"idProceso":..., "despacho":..., "fechaUltimaActuacion":..., "sujetosProcesales":...}], ...}`. Lista vacía si no existe.
- Actuaciones: `GET {BASE}/Proceso/Actuaciones/<idProceso>?pagina=1` devuelve `{"actuaciones":[{"idRegActuacion", "fechaActuacion", "actuacion", "anotacion", "fechaRegistro", "fechaInicial", "fechaFinal", ...}]}` de la más reciente a la más antigua. Una página inexistente o un proceso sin actuaciones devuelve **HTTP 404** con `{"StatusCode":404,"Message":...}`.
- Detalle: `GET {BASE}/Proceso/Detalle/<idProceso>` devuelve `{"ultimaActualizacion": "2026-10-08T08:29:32.06", "fechaConsulta": ..., ...}`.
- `BASE = https://consultaprocesos.ramajudicial.gov.co:448/api/v2`
- Solo se pide la página 1 de actuaciones. Las nuevas siempre entran por arriba, así que la página 1 basta.

---

## Estructura de archivos

```
requirements.txt
pytest.ini
.gitignore
config.example.toml
README.md
scripts/ejecutar_ciclo.bat
consultor/__init__.py
consultor/__main__.py
consultor/models.py        tipos y constantes
consultor/comparator.py    reglas R1, R2 (lógica pura)
consultor/store.py         SQLite: histórico, bitácora, validación (R6, R8)
consultor/fetcher.py       API de la Rama Judicial (R3, R4, R7)
consultor/loader.py        fuente de radicados (Excel hoy)
consultor/reporter.py      Excel del reporte, lectura de decisiones, aviso
consultor/main.py          ciclo completo, R5, línea de comandos
tests/__init__.py
tests/utiles.py
tests/test_comparator.py
tests/test_store.py
tests/test_fetcher.py
tests/test_loader.py
tests/test_reporter.py
tests/test_main.py
```

---

### Task 0: Entorno y esqueleto

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `consultor/__init__.py`, `tests/__init__.py`, `tests/utiles.py`

- [ ] **Step 1: Crear los archivos de configuración del proyecto**

`requirements.txt`:
```
requests>=2.32
openpyxl>=3.1
pytest>=8.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
datos/
reportes/
config.toml
```

`consultor/__init__.py` y `tests/__init__.py`: archivos vacíos.

- [ ] **Step 2: Crear `tests/utiles.py`**

```python
from datetime import datetime, timedelta

from consultor.models import EXITOSA, Actuacion, Consulta


def act(i, fecha="2026-05-15", texto="Al despacho", radicado="11001400307720210114700", anotacion=""):
    return Actuacion(
        id_reg_actuacion=i,
        radicado=radicado,
        fecha_actuacion=fecha,
        actuacion=texto,
        anotacion=anotacion,
    )


def ok(*actuaciones, despacho="JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ"):
    return Consulta(
        EXITOSA,
        id_proceso=1,
        despacho=despacho,
        ultima_actualizacion="2026-10-08T08:29:32",
        actuaciones=tuple(actuaciones),
    )


class Reloj:
    def __init__(self, inicio=datetime(2026, 10, 12, 7, 0, 0)):
        self.actual = inicio

    def __call__(self):
        return self.actual

    def avanzar(self, dias=2):
        self.actual += timedelta(days=dias)
```

- [ ] **Step 3: Crear `consultor/models.py`**

```python
from dataclasses import dataclass

EXITOSA = "Exitosa"
FALLIDA = "Fallida"
ERROR = "Error"

POSIBLE_NOVEDAD = "POSIBLE NOVEDAD"
SIN_CAMBIO = "SIN CAMBIO"
NO_VERIFICADO = "NO VERIFICADO"

PENDIENTE = "Pendiente"
CONFIRMADA = "Confirmada"
DESCARTADA = "Descartada"


@dataclass(frozen=True)
class Radicado:
    radicado: str
    empresa: str = ""
    despacho: str = ""
    calidad: str = ""


@dataclass(frozen=True)
class Actuacion:
    id_reg_actuacion: int
    radicado: str
    fecha_actuacion: str
    actuacion: str
    anotacion: str = ""
    fecha_registro: str = ""
    fecha_inicial: str = ""
    fecha_final: str = ""


@dataclass(frozen=True)
class Consulta:
    """Lo que devolvió el portal para un radicado. falla_portal cuenta para R5."""

    estado: str
    motivo: str = ""
    falla_portal: bool = False
    id_proceso: int | None = None
    despacho: str = ""
    ultima_actualizacion: str = ""
    actuaciones: tuple[Actuacion, ...] = ()


@dataclass(frozen=True)
class Veredicto:
    resultado: str
    nuevas: tuple[Actuacion, ...] = ()
    motivo: str = ""
```

- [ ] **Step 4: Crear el entorno e instalar**

Run:
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -c "import consultor.models, tests.utiles; print('ok')"
```
Expected: imprime `ok`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pytest.ini .gitignore consultor tests
git commit -m "chore: esqueleto del proyecto y modelos" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 1: comparator (R1, R2)

**Files:**
- Create: `consultor/comparator.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_comparator.py`:
```python
from consultor.comparator import comparar
from consultor.models import (
    FALLIDA,
    NO_VERIFICADO,
    POSIBLE_NOVEDAD,
    SIN_CAMBIO,
    Consulta,
)
from tests.utiles import act, ok


def test_primera_consulta_es_referencia_sin_alerta():
    v = comparar(ok(act(1), act(2)), conocidas=set(), tiene_referencia=False)
    assert v.resultado == SIN_CAMBIO
    assert v.nuevas == ()


def test_actuacion_nueva_es_posible_novedad():
    v = comparar(ok(act(3), act(2), act(1)), {1, 2}, True)
    assert v.resultado == POSIBLE_NOVEDAD
    assert [a.id_reg_actuacion for a in v.nuevas] == [3]


def test_varias_nuevas_se_reportan_todas():
    v = comparar(ok(act(4), act(3), act(1)), {1}, True)
    assert [a.id_reg_actuacion for a in v.nuevas] == [4, 3]


def test_sin_cambios():
    v = comparar(ok(act(2), act(1)), {1, 2}, True)
    assert v.resultado == SIN_CAMBIO
    assert v.nuevas == ()


def test_consulta_fallida_es_no_verificado_con_motivo():
    v = comparar(Consulta(FALLIDA, motivo="sin resultados"), set(), True)
    assert v.resultado == NO_VERIFICADO
    assert v.motivo == "sin resultados"


def test_misma_fecha_distinta_actuacion_se_detecta():
    # CA2: una actuación nueva con la misma fecha que la última no se puede perder
    v = comparar(ok(act(2, fecha="2026-05-15"), act(1, fecha="2026-05-15")), {1}, True)
    assert v.resultado == POSIBLE_NOVEDAD
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_comparator.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.comparator'`.

- [ ] **Step 3: Implementar**

`consultor/comparator.py`:
```python
from .models import (
    EXITOSA,
    NO_VERIFICADO,
    POSIBLE_NOVEDAD,
    SIN_CAMBIO,
    Consulta,
    Veredicto,
)


def comparar(consulta: Consulta, conocidas: set[int], tiene_referencia: bool) -> Veredicto:
    """Clasifica una consulta. No toca red ni disco."""
    if consulta.estado != EXITOSA:
        return Veredicto(NO_VERIFICADO, motivo=consulta.motivo)
    if not tiene_referencia:
        return Veredicto(SIN_CAMBIO, motivo="referencia inicial")  # R2
    nuevas = tuple(a for a in consulta.actuaciones if a.id_reg_actuacion not in conocidas)
    if nuevas:
        return Veredicto(POSIBLE_NOVEDAD, nuevas=nuevas)  # R1
    return Veredicto(SIN_CAMBIO)
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_comparator.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add consultor/comparator.py tests/test_comparator.py
git commit -m "feat: comparator con reglas R1 y R2" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: store (SQLite, R6, R8)

**Files:**
- Create: `consultor/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_store.py`:
```python
from datetime import datetime

import pytest

from consultor.models import (
    CONFIRMADA,
    DESCARTADA,
    FALLIDA,
    NO_VERIFICADO,
    PENDIENTE,
    POSIBLE_NOVEDAD,
    SIN_CAMBIO,
    Consulta,
    Radicado,
    Veredicto,
)
from consultor.store import Store
from tests.utiles import act, ok

AHORA = datetime(2026, 10, 12, 7, 0, 0)
R = Radicado("11001400307720210114700", empresa="ICEIN")


@pytest.fixture
def store():
    s = Store(":memory:")
    s.registrar_radicado(R)
    return s


def _con_novedad(store):
    c1 = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c1, R.radicado, ok(act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    store.cerrar_ciclo(c1, "Completo", AHORA)
    c2 = store.iniciar_ciclo(AHORA)
    nueva = act(2, fecha="2026-06-01", texto="Memorial")
    store.registrar_resultado(
        c2,
        R.radicado,
        ok(nueva, act(1)),
        Veredicto(POSIBLE_NOVEDAD, nuevas=(nueva,)),
        "2026-05-15: Al despacho",
        AHORA,
    )
    return c2


def test_iniciar_ciclo_reutiliza_el_ciclo_abierto_del_mismo_dia(store):
    a = store.iniciar_ciclo(AHORA)
    assert store.iniciar_ciclo(AHORA) == a


def test_ciclo_cerrado_no_se_reutiliza(store):
    a = store.iniciar_ciclo(AHORA)
    store.cerrar_ciclo(a, "Completo", AHORA)
    assert store.iniciar_ciclo(AHORA) != a


def test_resultado_guarda_actuaciones_y_marca_referencia(store):
    c = store.iniciar_ciclo(AHORA)
    assert not store.tiene_referencia(R.radicado)
    store.registrar_resultado(c, R.radicado, ok(act(1), act(2)), Veredicto(SIN_CAMBIO), "", AHORA)
    assert store.ids_conocidos(R.radicado) == {1, 2}
    assert store.tiene_referencia(R.radicado)
    assert store.ya_consultado(c, R.radicado)


def test_consulta_fallida_no_crea_referencia(store):
    c = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(
        c,
        R.radicado,
        Consulta(FALLIDA, motivo="sin resultados"),
        Veredicto(NO_VERIFICADO, motivo="sin resultados"),
        "",
        AHORA,
    )
    assert not store.tiene_referencia(R.radicado)
    assert store.ids_conocidos(R.radicado) == set()


def test_novedad_crea_alerta_pendiente_con_sus_datos(store):
    c2 = _con_novedad(store)
    filas = store.filas_reporte(c2)
    assert len(filas) == 1
    f = filas[0]
    assert f["resultado"] == POSIBLE_NOVEDAD
    assert f["decision"] == PENDIENTE
    assert f["detectada"] == "Memorial"
    assert f["anterior"] == "2026-05-15: Al despacho"
    assert f["empresa"] == "ICEIN"


def test_decision_solo_desde_pendiente_y_se_conserva_la_primera(store):
    c2 = _con_novedad(store)
    alerta_id = store.filas_reporte(c2)[0]["alerta_id"]
    assert store.registrar_decision(alerta_id, DESCARTADA, "Alisson", AHORA) is True
    assert store.registrar_decision(alerta_id, CONFIRMADA, "Otra persona", AHORA) is False
    f = store.filas_reporte(c2)[0]
    assert f["decision"] == DESCARTADA
    assert f["validada_por"] == "Alisson"


def test_decision_invalida_lanza_error(store):
    with pytest.raises(ValueError):
        store.registrar_decision(1, "Quizás", "Alisson", AHORA)


def test_resumen_cuenta_consultas(store):
    c2 = _con_novedad(store)
    assert store.resumen(c2) == {"total": 1, "exitosas": 1, "fallidas": 0, "novedades": 1}


def test_ultima_actuacion_devuelve_la_mas_reciente(store):
    c = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(
        c,
        R.radicado,
        ok(act(2, fecha="2026-06-01", texto="Memorial"), act(1, fecha="2026-05-15")),
        Veredicto(SIN_CAMBIO),
        "",
        AHORA,
    )
    assert store.ultima_actuacion(R.radicado) == "2026-06-01: Memorial"
    assert store.ultima_actuacion("00000000000000000000000") == ""
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.store'`.

- [ ] **Step 3: Implementar**

`consultor/store.py`:
```python
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import (
    CONFIRMADA,
    DESCARTADA,
    EXITOSA,
    PENDIENTE,
    POSIBLE_NOVEDAD,
    Consulta,
    Radicado,
    Veredicto,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS radicado (
    radicado TEXT PRIMARY KEY, empresa TEXT, despacho TEXT, id_proceso INTEGER);
CREATE TABLE IF NOT EXISTS actuacion (
    id_reg_actuacion INTEGER PRIMARY KEY, radicado TEXT NOT NULL,
    fecha_actuacion TEXT, actuacion TEXT, anotacion TEXT, fecha_registro TEXT,
    fecha_inicial TEXT, fecha_final TEXT, primera_vez_visto TEXT);
CREATE INDEX IF NOT EXISTS ix_actuacion_radicado ON actuacion(radicado);
CREATE TABLE IF NOT EXISTS ciclo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT NOT NULL, fin TEXT,
    estado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS consulta (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ciclo_id INTEGER NOT NULL,
    radicado TEXT NOT NULL, hora TEXT NOT NULL, estado TEXT NOT NULL,
    resultado TEXT NOT NULL, motivo TEXT, despacho TEXT, ultima_actualizacion TEXT,
    UNIQUE (ciclo_id, radicado));
CREATE TABLE IF NOT EXISTS alerta (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ciclo_id INTEGER NOT NULL,
    radicado TEXT NOT NULL, id_reg_actuacion INTEGER NOT NULL UNIQUE,
    anterior TEXT, estado TEXT NOT NULL, validada_por TEXT, validada_en TEXT);
"""

CONSULTAS_SQL = """
SELECT c.radicado, c.estado, c.resultado, c.motivo, c.hora,
       COALESCE(NULLIF(c.despacho, ''), r.despacho, '') AS despacho,
       r.empresa AS empresa
FROM consulta c JOIN radicado r ON r.radicado = c.radicado
WHERE c.ciclo_id = ? ORDER BY c.id
"""

ALERTAS_SQL = """
SELECT a.id, a.radicado, a.anterior, a.estado, a.validada_por, a.validada_en,
       t.fecha_actuacion, t.actuacion, t.anotacion
FROM alerta a JOIN actuacion t ON t.id_reg_actuacion = a.id_reg_actuacion
WHERE a.ciclo_id = ? ORDER BY a.id
"""


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


class Store:
    def __init__(self, ruta):
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(ruta))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)

    # ciclos
    def iniciar_ciclo(self, ahora: datetime) -> int:
        """Continúa el ciclo abierto del mismo día si existe (reanudación)."""
        fila = self.con.execute(
            "SELECT id FROM ciclo WHERE estado = 'En curso' AND substr(inicio, 1, 10) = ?",
            (ahora.date().isoformat(),),
        ).fetchone()
        if fila:
            return fila["id"]
        with self.con:
            cur = self.con.execute(
                "INSERT INTO ciclo (inicio, estado) VALUES (?, 'En curso')", (_iso(ahora),)
            )
        return cur.lastrowid

    def cerrar_ciclo(self, ciclo_id: int, estado: str, ahora: datetime) -> None:
        with self.con:
            self.con.execute(
                "UPDATE ciclo SET fin = ?, estado = ? WHERE id = ?",
                (_iso(ahora), estado, ciclo_id),
            )

    # lectura
    def registrar_radicado(self, r: Radicado) -> None:
        with self.con:
            self.con.execute(
                "INSERT INTO radicado (radicado, empresa, despacho) VALUES (?, ?, ?) "
                "ON CONFLICT(radicado) DO UPDATE SET "
                "empresa = excluded.empresa, despacho = excluded.despacho",
                (r.radicado, r.empresa, r.despacho),
            )

    def ya_consultado(self, ciclo_id: int, radicado: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM consulta WHERE ciclo_id = ? AND radicado = ?",
                (ciclo_id, radicado),
            ).fetchone()
            is not None
        )

    def ids_conocidos(self, radicado: str) -> set[int]:
        filas = self.con.execute(
            "SELECT id_reg_actuacion FROM actuacion WHERE radicado = ?", (radicado,)
        )
        return {f["id_reg_actuacion"] for f in filas}

    def tiene_referencia(self, radicado: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM consulta WHERE radicado = ? AND estado = ? LIMIT 1",
                (radicado, EXITOSA),
            ).fetchone()
            is not None
        )

    def ultima_actuacion(self, radicado: str) -> str:
        f = self.con.execute(
            "SELECT fecha_actuacion, actuacion FROM actuacion WHERE radicado = ? "
            "ORDER BY fecha_actuacion DESC, id_reg_actuacion DESC LIMIT 1",
            (radicado,),
        ).fetchone()
        return f"{f['fecha_actuacion']}: {f['actuacion']}" if f else ""

    # escritura
    def registrar_resultado(
        self,
        ciclo_id: int,
        radicado: str,
        consulta: Consulta,
        veredicto: Veredicto,
        anterior: str,
        ahora: datetime,
    ) -> None:
        """Guarda actuaciones, consulta y alertas en una sola transacción.

        Si el proceso se cae a la mitad no queda una actuación conocida sin su alerta.
        """
        hora = _iso(ahora)
        with self.con:
            if consulta.estado == EXITOSA:
                self.con.executemany(
                    "INSERT OR IGNORE INTO actuacion (id_reg_actuacion, radicado, "
                    "fecha_actuacion, actuacion, anotacion, fecha_registro, "
                    "fecha_inicial, fecha_final, primera_vez_visto) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            a.id_reg_actuacion,
                            radicado,
                            a.fecha_actuacion,
                            a.actuacion,
                            a.anotacion,
                            a.fecha_registro,
                            a.fecha_inicial,
                            a.fecha_final,
                            hora,
                        )
                        for a in consulta.actuaciones
                    ],
                )
                if consulta.id_proceso:
                    self.con.execute(
                        "UPDATE radicado SET id_proceso = ? WHERE radicado = ?",
                        (consulta.id_proceso, radicado),
                    )
            self.con.execute(
                "INSERT INTO consulta (ciclo_id, radicado, hora, estado, resultado, "
                "motivo, despacho, ultima_actualizacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ciclo_id,
                    radicado,
                    hora,
                    consulta.estado,
                    veredicto.resultado,
                    veredicto.motivo,
                    consulta.despacho,
                    consulta.ultima_actualizacion,
                ),
            )
            self.con.executemany(
                "INSERT OR IGNORE INTO alerta (ciclo_id, radicado, id_reg_actuacion, "
                "anterior, estado) VALUES (?, ?, ?, ?, ?)",
                [
                    (ciclo_id, radicado, a.id_reg_actuacion, anterior, PENDIENTE)
                    for a in veredicto.nuevas
                ],
            )

    def registrar_decision(
        self, alerta_id: int, estado: str, usuario: str, ahora: datetime
    ) -> bool:
        """Única puerta de escritura de decisiones. Solo cambia alertas Pendiente."""
        if estado not in (CONFIRMADA, DESCARTADA):
            raise ValueError(f"decisión inválida: {estado!r}")
        with self.con:
            cur = self.con.execute(
                "UPDATE alerta SET estado = ?, validada_por = ?, validada_en = ? "
                "WHERE id = ? AND estado = ?",
                (estado, usuario, _iso(ahora), alerta_id, PENDIENTE),
            )
        return cur.rowcount == 1

    # salida
    def resumen(self, ciclo_id: int) -> dict:
        f = self.con.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(estado = ?), 0) AS exitosas, "
            "COALESCE(SUM(resultado = ?), 0) AS novedades "
            "FROM consulta WHERE ciclo_id = ?",
            (EXITOSA, POSIBLE_NOVEDAD, ciclo_id),
        ).fetchone()
        return {
            "total": f["total"],
            "exitosas": f["exitosas"],
            "fallidas": f["total"] - f["exitosas"],
            "novedades": f["novedades"],
        }

    def filas_reporte(self, ciclo_id: int) -> list[dict]:
        alertas: dict[str, list] = {}
        for a in self.con.execute(ALERTAS_SQL, (ciclo_id,)):
            alertas.setdefault(a["radicado"], []).append(a)
        filas = []
        for c in self.con.execute(CONSULTAS_SQL, (ciclo_id,)):
            base = {
                "alerta_id": None,
                "empresa": c["empresa"] or "",
                "radicado": c["radicado"],
                "despacho": c["despacho"] or "",
                "estado_consulta": c["estado"],
                "resultado": c["resultado"],
                "anterior": "",
                "fecha_detectada": "",
                "detectada": "",
                "anotacion": "",
                "hora": c["hora"],
                "motivo": c["motivo"] or "",
                "decision": "",
                "validada_por": "",
                "validada_en": "",
            }
            if c["resultado"] == POSIBLE_NOVEDAD:
                for a in alertas.get(c["radicado"], []):
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
            else:
                filas.append(base)
        return filas
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_store.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add consultor/store.py tests/test_store.py
git commit -m "feat: store SQLite con histórico, bitácora y decisiones" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: fetcher (R3, R4, R7)

**Files:**
- Create: `consultor/fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_fetcher.py`:
```python
import requests

from consultor.fetcher import Fetcher
from consultor.models import ERROR, EXITOSA, FALLIDA, Radicado

RAD = Radicado("11001400307720210114700")

BUSQUEDA = {
    "procesos": [
        {
            "idProceso": 108832900,
            "despacho": "JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ ",
            "fechaUltimaActuacion": "2026-05-15T00:00:00",
            "sujetosProcesales": "Demandante: PERSONA UNO | Demandado: EMPRESA",
        }
    ]
}
ACTUACIONES = {
    "actuaciones": [
        {
            "idRegActuacion": 2710288320,
            "fechaActuacion": "2026-05-15T00:00:00",
            "actuacion": "Al despacho",
            "anotacion": None,
            "fechaInicial": None,
            "fechaFinal": None,
            "fechaRegistro": "2026-05-15T00:00:00",
        },
        {
            "idRegActuacion": 2702295560,
            "fechaActuacion": "2026-04-29T00:00:00",
            "actuacion": "Recepción memorial",
            "anotacion": "ALLEGAN RECURSO/OR",
            "fechaInicial": None,
            "fechaFinal": None,
            "fechaRegistro": "2026-04-29T00:00:00",
        },
    ]
}
DETALLE = {"ultimaActualizacion": "2026-10-08T08:29:32.06"}


class RespuestaFalsa:
    def __init__(self, status=200, datos=None, json_invalido=False):
        self.status_code = status
        self.datos = datos
        self.json_invalido = json_invalido

    def json(self):
        if self.json_invalido:
            raise ValueError("no es JSON")
        return self.datos


class SesionFalsa:
    """Responde según un fragmento de la URL. Una lista se consume de a una respuesta."""

    def __init__(self, rutas):
        self.rutas = rutas
        self.llamadas = []

    def get(self, url, params=None, timeout=None):
        self.llamadas.append((url, params))
        for fragmento, resp in self.rutas.items():
            if fragmento in url:
                if isinstance(resp, list):
                    resp = resp.pop(0)
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"llamada no esperada: {url}")


def crear(rutas, reintentos=3):
    dormidos = []
    sesion = SesionFalsa(rutas)
    f = Fetcher(sesion=sesion, pausa=1.0, reintentos=reintentos, espera=2.0, dormir=dormidos.append)
    return f, sesion, dormidos


def rutas_ok():
    return {
        "NumeroRadicacion": RespuestaFalsa(200, BUSQUEDA),
        "Actuaciones": RespuestaFalsa(200, ACTUACIONES),
        "Detalle": RespuestaFalsa(200, DETALLE),
    }


def test_consulta_exitosa_devuelve_actuaciones_normalizadas():
    f, sesion, _ = crear(rutas_ok())
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.id_proceso == 108832900
    assert c.despacho == "JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ"
    assert c.ultima_actualizacion == "2026-10-08T08:29:32.06"
    a = c.actuaciones[0]
    assert (a.id_reg_actuacion, a.fecha_actuacion, a.actuacion, a.anotacion) == (
        2710288320,
        "2026-05-15",
        "Al despacho",
        "",
    )
    assert c.actuaciones[1].anotacion == "ALLEGAN RECURSO/OR"


def test_siempre_pide_solo_activos_false():
    f, sesion, _ = crear(rutas_ok())
    f.consultar(RAD)
    url, params = sesion.llamadas[0]
    assert params["SoloActivos"] == "false"
    assert params["numero"] == RAD.radicado


def test_busqueda_vacia_es_sin_resultados_y_no_es_falla_del_portal():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, {"procesos": []})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA
    assert c.motivo == "sin resultados"
    assert c.falla_portal is False


def test_radicado_invalido_no_llama_al_portal():
    f, sesion, _ = crear(rutas_ok())
    c = f.consultar(Radicado("123"))
    assert c.estado == FALLIDA
    assert "23 dígitos" in c.motivo
    assert c.falla_portal is False
    assert sesion.llamadas == []


def test_actuaciones_404_es_proceso_sin_actuaciones():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, {"StatusCode": 404})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.actuaciones == ()


def test_reintenta_con_espera_creciente_y_se_recupera():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = [RespuestaFalsa(500), RespuestaFalsa(200, BUSQUEDA)]
    f, _, dormidos = crear(rutas)
    assert f.consultar(RAD).estado == EXITOSA
    assert dormidos == [2.0]


def test_portal_caido_agota_reintentos_y_cuenta_como_falla():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = requests.Timeout("lento")
    f, sesion, dormidos = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA
    assert c.falla_portal is True
    assert "Timeout" in c.motivo
    assert len(sesion.llamadas) == 3
    assert dormidos == [2.0, 4.0]


def test_respuesta_que_no_es_json_se_reintenta():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, json_invalido=True)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def test_forma_inesperada_es_error():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(200, {"otra_cosa": []})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == ERROR
    assert c.falla_portal is True


def test_falla_del_detalle_no_tumba_la_consulta():
    rutas = rutas_ok()
    rutas["Detalle"] = RespuestaFalsa(500)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.ultima_actualizacion == ""


def test_pausar_duerme_el_tiempo_configurado():
    f, _, dormidos = crear(rutas_ok())
    f.pausar()
    assert dormidos == [1.0]
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.fetcher'`.

- [ ] **Step 3: Implementar**

`consultor/fetcher.py`:
```python
import re
import time

import requests

from .models import ERROR, EXITOSA, FALLIDA, Actuacion, Consulta, Radicado

BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
RADICADO_RE = re.compile(r"^\d{23}$")


class ErrorPortal(Exception):
    """El portal no respondió bien tras agotar los reintentos."""


def _fecha(valor) -> str:
    return (valor or "")[:10]


def _actuacion(a: dict, radicado: str) -> Actuacion:
    return Actuacion(
        id_reg_actuacion=a["idRegActuacion"],
        radicado=radicado,
        fecha_actuacion=_fecha(a["fechaActuacion"]),
        actuacion=(a.get("actuacion") or "").strip(),
        anotacion=(a.get("anotacion") or "").strip(),
        fecha_registro=_fecha(a.get("fechaRegistro")),
        fecha_inicial=_fecha(a.get("fechaInicial")),
        fecha_final=_fecha(a.get("fechaFinal")),
    )


class Fetcher:
    """Único módulo que conoce la Rama Judicial. Descarta sujetosProcesales (datos personales)."""

    def __init__(
        self,
        sesion=None,
        pausa=1.0,
        reintentos=3,
        espera=2.0,
        timeout=30,
        dormir=time.sleep,
    ):
        self.sesion = sesion or requests.Session()
        self.pausa = pausa
        self.reintentos = reintentos
        self.espera = espera
        self.timeout = timeout
        self.dormir = dormir

    def pausar(self) -> None:
        self.dormir(self.pausa)

    def _get(self, url, params=None):
        """GET con reintentos y espera creciente. Un 404 no se reintenta."""
        motivo = ""
        for intento in range(self.reintentos):
            try:
                resp = self.sesion.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                motivo = type(e).__name__
            else:
                if resp.status_code == 404:
                    return 404, None
                if resp.status_code == 200:
                    try:
                        return 200, resp.json()
                    except ValueError:
                        motivo = "respuesta que no es JSON"
                else:
                    motivo = f"HTTP {resp.status_code}"
            if intento < self.reintentos - 1:
                self.dormir(self.espera * (2**intento))
        raise ErrorPortal(motivo)

    def _ultima_actualizacion(self, id_proceso) -> str:
        try:
            estado, datos = self._get(f"{BASE}/Proceso/Detalle/{id_proceso}")
        except ErrorPortal:
            return ""
        if estado != 200 or not isinstance(datos, dict):
            return ""
        return datos.get("ultimaActualizacion") or ""

    def consultar(self, r: Radicado) -> Consulta:
        if not RADICADO_RE.match(r.radicado):
            return Consulta(FALLIDA, motivo="radicado inválido: debe tener 23 dígitos")
        try:
            estado, datos = self._get(
                f"{BASE}/Procesos/Consulta/NumeroRadicacion",
                {"numero": r.radicado, "SoloActivos": "false", "pagina": 1},
            )
            procesos = (datos or {}).get("procesos") or []
            if estado == 404 or not procesos:
                return Consulta(FALLIDA, motivo="sin resultados")
            proceso = procesos[0]
            id_proceso = proceso["idProceso"]
            estado, datos = self._get(
                f"{BASE}/Proceso/Actuaciones/{id_proceso}", {"pagina": 1}
            )
            lista = [] if estado == 404 else datos["actuaciones"]
            return Consulta(
                EXITOSA,
                id_proceso=id_proceso,
                despacho=(proceso.get("despacho") or "").strip(),
                ultima_actualizacion=self._ultima_actualizacion(id_proceso),
                actuaciones=tuple(_actuacion(a, r.radicado) for a in lista),
            )
        except ErrorPortal as e:
            return Consulta(FALLIDA, motivo=str(e), falla_portal=True)
        except (KeyError, TypeError, AttributeError) as e:
            return Consulta(
                ERROR,
                motivo=f"respuesta inesperada: {type(e).__name__} {e}",
                falla_portal=True,
            )
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add consultor/fetcher.py tests/test_fetcher.py
git commit -m "feat: fetcher contra la API de la Rama Judicial" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: loader (fuente intercambiable)

**Files:**
- Create: `consultor/loader.py`
- Test: `tests/test_loader.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_loader.py`:
```python
import pytest
from openpyxl import Workbook

from consultor.loader import FuenteExcel, crear_fuente

ENC = ["Radicado", "Empresa", "Despacho", "Calidad", "Estado"]


def hacer_excel(ruta, filas, encabezado=ENC, hoja="GENERAL"):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append(encabezado)
    for f in filas:
        ws.append(f)
    wb.save(ruta)


def fuente(ruta, **extra):
    return FuenteExcel(
        ruta=ruta,
        hoja="GENERAL",
        col_radicado="Radicado",
        col_empresa="Empresa",
        col_despacho="Despacho",
        col_calidad="Calidad",
        col_estado="Estado",
        **extra,
    )


def test_lee_radicados_con_sus_datos(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [["11001400307720210114700", "ICEIN", "Juzgado 77", "Demandado", "Activo"]])
    r = fuente(ruta).cargar()[0]
    assert (r.radicado, r.empresa, r.despacho, r.calidad) == (
        "11001400307720210114700",
        "ICEIN",
        "Juzgado 77",
        "Demandado",
    )


def test_limpia_espacios_y_guiones_del_radicado(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[" 11001-40-03-077-2021-01147-00 ", "ICEIN", "", "", "Activo"]])
    assert fuente(ruta).cargar()[0].radicado == "11001400307720210114700"


def test_duplicado_une_las_empresas(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
            ["11001400307720210114700", "COHERPA", "", "", "Activo"],
        ],
    )
    radicados = fuente(ruta).cargar()
    assert len(radicados) == 1
    assert radicados[0].empresa == "ICEIN / COHERPA"


def test_filas_vacias_se_saltan_pero_los_invalidos_se_conservan(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [[None, None, None, None, None], ["123", "ICEIN", "", "", "Activo"]])
    radicados = fuente(ruta).cargar()
    assert [r.radicado for r in radicados] == ["123"]


def test_filtra_por_estado_si_se_configura(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(
        ruta,
        [
            ["11001400307720210114700", "ICEIN", "", "", "Activo"],
            ["11001400307720210114701", "ICEIN", "", "", "Cerrado"],
        ],
    )
    radicados = fuente(ruta, estados_incluidos=["activo"]).cargar()
    assert [r.radicado for r in radicados] == ["11001400307720210114700"]


def test_columna_inexistente_da_un_error_claro(tmp_path):
    ruta = tmp_path / "x.xlsx"
    hacer_excel(ruta, [], encabezado=["Otra"])
    with pytest.raises(ValueError, match="Radicado"):
        fuente(ruta).cargar()


def test_crear_fuente_excel_y_tipo_desconocido(tmp_path):
    cfg = {"tipo": "excel", "ruta": str(tmp_path / "x.xlsx"), "hoja": "GENERAL", "col_radicado": "Radicado"}
    assert isinstance(crear_fuente(cfg), FuenteExcel)
    with pytest.raises(ValueError, match="sql"):
        crear_fuente({"tipo": "sql"})
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_loader.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.loader'`.

- [ ] **Step 3: Implementar**

`consultor/loader.py`:
```python
import re

from openpyxl import load_workbook

from .models import Radicado


def _radicado(valor) -> str:
    return re.sub(r"[\s\-\.]", "", str(valor)) if valor is not None else ""


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _indice(encabezado: list[str], nombre: str, hoja: str) -> int:
    try:
        return encabezado.index(nombre)
    except ValueError:
        raise ValueError(f"No encuentro la columna '{nombre}' en la hoja '{hoja}'") from None


class FuenteExcel:
    """Lee los radicados de un Excel, solo lectura (R9).

    Contrato de cualquier fuente: un objeto con cargar() -> list[Radicado].
    No descarta radicados inválidos: el fetcher los marca NO VERIFICADO (R3).
    """

    def __init__(
        self,
        ruta,
        hoja,
        col_radicado,
        col_empresa="",
        col_despacho="",
        col_calidad="",
        col_estado="",
        estados_incluidos=(),
    ):
        self.ruta = ruta
        self.hoja = hoja
        self.col_radicado = col_radicado
        self.col_empresa = col_empresa
        self.col_despacho = col_despacho
        self.col_calidad = col_calidad
        self.col_estado = col_estado
        self.estados = {e.strip().lower() for e in estados_incluidos}

    def cargar(self) -> list[Radicado]:
        wb = load_workbook(self.ruta, read_only=True, data_only=True)
        try:
            filas = wb[self.hoja].iter_rows(values_only=True)
            enc = [_texto(c) for c in next(filas)]
            i_rad = _indice(enc, self.col_radicado, self.hoja)
            i_emp = _indice(enc, self.col_empresa, self.hoja) if self.col_empresa else None
            i_des = _indice(enc, self.col_despacho, self.hoja) if self.col_despacho else None
            i_cal = _indice(enc, self.col_calidad, self.hoja) if self.col_calidad else None
            i_est = _indice(enc, self.col_estado, self.hoja) if self.estados else None

            def celda(fila, i):
                return _texto(fila[i]) if i is not None and i < len(fila) else ""

            por_radicado: dict[str, Radicado] = {}
            for fila in filas:
                rad = _radicado(fila[i_rad]) if i_rad < len(fila) else ""
                if not rad:
                    continue
                if self.estados and celda(fila, i_est).lower() not in self.estados:
                    continue
                nuevo = Radicado(rad, celda(fila, i_emp), celda(fila, i_des), celda(fila, i_cal))
                previo = por_radicado.get(rad)
                if previo is None:
                    por_radicado[rad] = nuevo
                elif nuevo.empresa and nuevo.empresa not in previo.empresa.split(" / "):
                    empresas = " / ".join(e for e in (previo.empresa, nuevo.empresa) if e)
                    por_radicado[rad] = Radicado(rad, empresas, previo.despacho, previo.calidad)
            return list(por_radicado.values())
        finally:
            wb.close()


def crear_fuente(cfg: dict):
    tipo = cfg.get("tipo")
    if tipo == "excel":
        return FuenteExcel(
            ruta=cfg["ruta"],
            hoja=cfg["hoja"],
            col_radicado=cfg["col_radicado"],
            col_empresa=cfg.get("col_empresa", ""),
            col_despacho=cfg.get("col_despacho", ""),
            col_calidad=cfg.get("col_calidad", ""),
            col_estado=cfg.get("col_estado", ""),
            estados_incluidos=cfg.get("estados_incluidos", ()),
        )
    raise ValueError(f"fuente desconocida: {tipo}")
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_loader.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add consultor/loader.py tests/test_loader.py
git commit -m "feat: loader con fuente Excel intercambiable" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: reporter (Excel, lectura de decisiones, aviso)

**Files:**
- Create: `consultor/reporter.py`
- Test: `tests/test_reporter.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_reporter.py`:
```python
from datetime import datetime

from openpyxl import load_workbook

from consultor.models import NO_VERIFICADO, POSIBLE_NOVEDAD, SIN_CAMBIO
from consultor.reporter import LEYENDA, avisar, escribir_reporte, leer_decisiones

AHORA = datetime(2026, 10, 12, 7, 0, 0)
RESUMEN = {"total": 3, "exitosas": 2, "fallidas": 1, "novedades": 1, "estado": "Completo"}


def fila(**kw):
    base = dict(
        alerta_id=None,
        empresa="ICEIN",
        radicado="11001400307720210114700",
        despacho="JUZGADO 077",
        estado_consulta="Exitosa",
        resultado=SIN_CAMBIO,
        anterior="",
        fecha_detectada="",
        detectada="",
        anotacion="",
        hora="2026-10-12T07:00:00",
        motivo="",
        decision="",
        validada_por="",
        validada_en="",
    )
    base.update(kw)
    return base


def novedad(alerta_id=7, **kw):
    return fila(
        alerta_id=alerta_id,
        resultado=POSIBLE_NOVEDAD,
        detectada="Auto",
        fecha_detectada="2026-10-10",
        decision="Pendiente",
        **kw,
    )


def escribir(tmp_path, filas):
    return escribir_reporte(filas, RESUMEN, tmp_path, 3, AHORA)


def valores(hoja):
    return [[c.value for c in f] for f in hoja.iter_rows()]


def test_reporte_tiene_tres_hojas_y_la_leyenda(tmp_path):
    ruta = escribir(tmp_path, [fila()])
    wb = load_workbook(ruta)
    assert wb.sheetnames == ["Resumen", "Alertas", "Sin cambio"]
    textos = [str(c.value) for f in wb["Resumen"].iter_rows() for c in f]
    assert LEYENDA in textos
    assert ruta.name == "reporte_ciclo_0003_2026-10-12.xlsx"


def test_novedades_primero_y_sin_cambio_en_su_hoja(tmp_path):
    filas = [fila(), fila(resultado=NO_VERIFICADO, motivo="sin resultados"), novedad()]
    wb = load_workbook(escribir(tmp_path, filas))
    enc = valores(wb["Alertas"])[0]
    resultados = [f[enc.index("Resultado")] for f in valores(wb["Alertas"])[1:]]
    assert resultados == [POSIBLE_NOVEDAD, NO_VERIFICADO]
    sin = valores(wb["Sin cambio"])
    assert [f[enc.index("Resultado")] for f in sin[1:]] == [SIN_CAMBIO]


def test_formula_en_la_anotacion_se_guarda_como_texto(tmp_path):
    wb = load_workbook(escribir(tmp_path, [novedad(anotacion="=1+1")]))
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    celda = hoja.cell(row=2, column=enc.index("Anotación detectada") + 1)
    assert celda.value == "=1+1"
    assert celda.data_type == "s"


def test_no_incluye_nombres_de_partes(tmp_path):
    wb = load_workbook(escribir(tmp_path, [novedad()]))
    encabezados = [c.value for c in wb["Alertas"][1]]
    assert not any("parte" in str(e).lower() or "sujeto" in str(e).lower() for e in encabezados)


def marcar(ruta, decision, valido_por):
    wb = load_workbook(ruta)
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    hoja.cell(row=2, column=enc.index("Decisión") + 1, value=decision)
    hoja.cell(row=2, column=enc.index("Validó") + 1, value=valido_por)
    wb.save(ruta)


def test_leer_decisiones_devuelve_solo_las_decididas(tmp_path):
    ruta = escribir(tmp_path, [novedad(alerta_id=7)])
    assert leer_decisiones(tmp_path) == []  # todo Pendiente
    marcar(ruta, "Confirmada", "Alisson Rengifo")
    assert leer_decisiones(tmp_path) == [(7, "Confirmada", "Alisson Rengifo")]


def test_validador_en_blanco_se_devuelve_vacio(tmp_path):
    ruta = escribir(tmp_path, [novedad(alerta_id=7)])
    marcar(ruta, "Descartada", None)
    assert leer_decisiones(tmp_path) == [(7, "Descartada", "")]


def test_archivo_ilegible_avisa_y_sigue(tmp_path):
    (tmp_path / "reporte_ciclo_0001_2026-10-10.xlsx").write_bytes(b"no es un excel")
    ruta = escribir(tmp_path, [novedad(alerta_id=7)])
    marcar(ruta, "Confirmada", "Alisson Rengifo")
    avisos = []
    assert leer_decisiones(tmp_path, avisos.append) == [(7, "Confirmada", "Alisson Rengifo")]
    assert any("reporte_ciclo_0001" in a for a in avisos)


def test_avisar_escribe_en_el_log(tmp_path, capsys):
    archivo = tmp_path / "carpeta" / "avisos.log"
    avisar("Ciclo 3 listo", archivo, AHORA)
    assert "2026-10-12 07:00:00 Ciclo 3 listo" in archivo.read_text(encoding="utf-8")
    assert "Ciclo 3 listo" in capsys.readouterr().out
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_reporter.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.reporter'`.

- [ ] **Step 3: Implementar**

`consultor/reporter.py`:
```python
import zipfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

from .models import CONFIRMADA, DESCARTADA, NO_VERIFICADO, POSIBLE_NOVEDAD, SIN_CAMBIO

FUENTE = "Consulta de Procesos Nacional Unificada"
ENLACE_PORTAL = "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion"
LEYENDA = (
    "Alerta automática. No constituye notificación procesal ni actuación confirmada; "
    "verificar en la fuente oficial."
)

ENCABEZADOS = [
    "ID alerta",
    "Empresa",
    "Radicado",
    "Despacho",
    "Estado de la consulta",
    "Resultado",
    "Actuación anterior",
    "Fecha actuación detectada",
    "Actuación detectada",
    "Anotación detectada",
    "Fecha y hora de consulta",
    "Fuente",
    "Enlace",
    "Motivo",
    "Decisión",
    "Validó",
    "Validada en",
]
ORDEN = {POSIBLE_NOVEDAD: 0, NO_VERIFICADO: 1, SIN_CAMBIO: 2}


def _valores(f: dict) -> list:
    return [
        f["alerta_id"],
        f["empresa"],
        f["radicado"],
        f["despacho"],
        f["estado_consulta"],
        f["resultado"],
        f["anterior"],
        f["fecha_detectada"],
        f["detectada"],
        f["anotacion"],
        f["hora"],
        FUENTE,
        ENLACE_PORTAL,
        f["motivo"],
        f["decision"],
        f["validada_por"],
        f["validada_en"],
    ]


def _agregar(hoja, valores: list) -> None:
    hoja.append(valores)
    for celda in hoja[hoja.max_row]:
        # un texto que empieza por "=" se guardaría como fórmula
        if isinstance(celda.value, str) and celda.value.startswith("="):
            celda.data_type = "s"


def escribir_reporte(filas, resumen: dict, carpeta, ciclo_id: int, ahora: datetime) -> Path:
    wb = Workbook()
    hoja_resumen = wb.active
    hoja_resumen.title = "Resumen"
    for linea in [
        ("Ciclo", ciclo_id),
        ("Fecha", ahora.strftime("%Y-%m-%d %H:%M")),
        ("Total consultados", resumen["total"]),
        ("Exitosos", resumen["exitosas"]),
        ("Fallidos", resumen["fallidas"]),
        ("Posibles novedades", resumen["novedades"]),
        ("Estado del ciclo", resumen["estado"]),
        ("", ""),
        ("Aviso", LEYENDA),
    ]:
        hoja_resumen.append(linea)

    alertas = wb.create_sheet("Alertas")
    sin_cambio = wb.create_sheet("Sin cambio")
    alertas.append(ENCABEZADOS)
    sin_cambio.append(ENCABEZADOS)
    for f in sorted(filas, key=lambda f: ORDEN[f["resultado"]]):
        _agregar(sin_cambio if f["resultado"] == SIN_CAMBIO else alertas, _valores(f))

    col = ENCABEZADOS.index("Decisión") + 1
    letra = alertas.cell(row=1, column=col).column_letter
    lista = DataValidation(type="list", formula1='"Pendiente,Confirmada,Descartada"', allow_blank=True)
    alertas.add_data_validation(lista)
    lista.add(f"{letra}2:{letra}{max(alertas.max_row, 500)}")
    alertas.freeze_panes = "A2"
    sin_cambio.freeze_panes = "A2"

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"reporte_ciclo_{ciclo_id:04d}_{ahora:%Y-%m-%d}.xlsx"
    wb.save(ruta)
    return ruta


def leer_decisiones(carpeta, avisar_fn=None) -> list[tuple[int, str, str]]:
    """Lee las decisiones que Alisson marcó en los reportes anteriores.

    Devuelve (alerta_id, decisión, validó). Un archivo ilegible (por ejemplo abierto
    en Excel) se avisa y se reintenta en el ciclo siguiente.
    """
    decisiones = []
    for ruta in sorted(Path(carpeta).glob("reporte_*.xlsx")):
        try:
            wb = load_workbook(ruta, read_only=True, data_only=True)
            try:
                filas = wb["Alertas"].iter_rows(values_only=True)
                enc = next(filas)
                i_id = enc.index("ID alerta")
                i_dec = enc.index("Decisión")
                i_val = enc.index("Validó")
                for f in filas:
                    if f[i_id] and f[i_dec] in (CONFIRMADA, DESCARTADA):
                        decisiones.append((int(f[i_id]), f[i_dec], f[i_val] or ""))
            finally:
                wb.close()
        except (OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as e:
            if avisar_fn:
                avisar_fn(
                    f"No se pudo leer {ruta.name} ({type(e).__name__}); "
                    "se reintenta en el próximo ciclo."
                )
    return decisiones


def avisar(texto: str, archivo, ahora: datetime) -> None:
    """Único punto de aviso. El canal real (correo o Teams) lo define Sistemas."""
    archivo = Path(archivo)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(f"{ahora:%Y-%m-%d %H:%M:%S} {texto}\n")
    print(texto)
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_reporter.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add consultor/reporter.py tests/test_reporter.py
git commit -m "feat: reporter Excel con decisión de Alisson y aviso" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: main (ciclo completo, R5, línea de comandos)

**Files:**
- Create: `consultor/main.py`, `consultor/__main__.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_main.py`:
```python
import pytest
from openpyxl import load_workbook

from consultor.main import MOTIVO_DETENIDO, correr_ciclo
from consultor.models import FALLIDA, Consulta, Radicado
from consultor.reporter import LEYENDA
from consultor.store import Store
from tests.utiles import Reloj, act, ok

R1 = Radicado("11001400307720210114700", empresa="ICEIN")


class FetcherFalso:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def consultar(self, r):
        self.llamadas.append(r.radicado)
        resp = self.respuestas[r.radicado]
        if isinstance(resp, Exception):
            raise resp
        return resp

    def pausar(self):
        pass


def correr(tmp_path, radicados, fetcher, store, reloj, avisos=None, max_fallas=0.5):
    avisos = [] if avisos is None else avisos
    return correr_ciclo(
        radicados, fetcher, store, tmp_path, "Alisson Rengifo", max_fallas, avisos.append, reloj
    )


def hoja_alertas(ruta):
    hoja = load_workbook(ruta)["Alertas"]
    enc = [c.value for c in hoja[1]]
    filas = [[c.value for c in f] for f in hoja.iter_rows(min_row=2)]
    return enc, filas


def dos_ciclos(tmp_path):
    store, reloj = Store(":memory:"), Reloj()
    f = FetcherFalso({R1.radicado: ok(act(1), act(2))})
    r1 = correr(tmp_path, [R1], f, store, reloj)
    reloj.avanzar()
    f.respuestas = {R1.radicado: ok(act(3, texto="Auto"), act(2), act(1))}
    r2 = correr(tmp_path, [R1], f, store, reloj)
    return store, reloj, f, r1, r2


def test_primera_vez_sin_alerta_y_luego_detecta_la_nueva(tmp_path):
    avisos = []
    store, reloj = Store(":memory:"), Reloj()
    f = FetcherFalso({R1.radicado: ok(act(1), act(2))})
    r1 = correr(tmp_path, [R1], f, store, reloj, avisos)
    assert (r1.total, r1.novedades, r1.estado) == (1, 0, "Completo")

    reloj.avanzar()
    f.respuestas = {R1.radicado: ok(act(3, texto="Auto"), act(2), act(1))}
    r2 = correr(tmp_path, [R1], f, store, reloj, avisos)
    assert r2.novedades == 1
    enc, filas = hoja_alertas(r2.reporte)
    assert filas[0][enc.index("Resultado")] == "POSIBLE NOVEDAD"
    assert filas[0][enc.index("Actuación detectada")] == "Auto"
    assert LEYENDA in avisos[-1]


def test_decision_de_alisson_se_registra_y_no_se_repite(tmp_path):
    store, reloj, f, r1, r2 = dos_ciclos(tmp_path)
    wb = load_workbook(r2.reporte)
    hoja = wb["Alertas"]
    enc = [c.value for c in hoja[1]]
    hoja.cell(row=2, column=enc.index("Decisión") + 1, value="Descartada")
    wb.save(r2.reporte)

    reloj.avanzar()
    r3 = correr(tmp_path, [R1], f, store, reloj)
    assert r3.novedades == 0  # R6: misma actuación, no alerta de nuevo
    anterior = store.filas_reporte(r2.ciclo_id)[0]
    assert anterior["decision"] == "Descartada"
    assert anterior["validada_por"] == "Alisson Rengifo"  # validador por defecto (CA5)


def test_r5_detiene_y_marca_el_resto_como_no_verificado(tmp_path):
    radicados = [Radicado(f"{i:023d}") for i in range(1, 13)]
    caida = Consulta(FALLIDA, motivo="HTTP 503", falla_portal=True)
    f = FetcherFalso({r.radicado: caida for r in radicados})
    store, avisos = Store(":memory:"), []
    res = correr(tmp_path, radicados, f, store, Reloj(), avisos)
    assert res.estado.startswith("Detenido")
    assert len(f.llamadas) == 10
    assert (res.total, res.exitosas, res.fallidas) == (12, 0, 12)
    assert any("Fuente no disponible" in a for a in avisos)
    motivos = [x["motivo"] for x in store.filas_reporte(res.ciclo_id)]
    assert motivos.count(MOTIVO_DETENIDO) == 2


def test_ciclo_interrumpido_se_reanuda_sin_repetir_consultas(tmp_path):
    rs = [Radicado(f"{i:023d}") for i in range(1, 4)]
    store, reloj = Store(":memory:"), Reloj()
    f = FetcherFalso(
        {rs[0].radicado: ok(act(1)), rs[1].radicado: ok(act(1)), rs[2].radicado: RuntimeError("red caída")}
    )
    with pytest.raises(RuntimeError):
        correr(tmp_path, rs, f, store, reloj)
    f2 = FetcherFalso({rs[2].radicado: ok(act(1))})
    res = correr(tmp_path, rs, f2, store, reloj)
    assert f2.llamadas == [rs[2].radicado]
    assert res.total == 3


def test_radicado_sin_resultados_queda_en_el_reporte_como_no_verificado(tmp_path):
    f = FetcherFalso({R1.radicado: Consulta(FALLIDA, motivo="sin resultados")})
    res = correr(tmp_path, [R1], f, Store(":memory:"), Reloj())
    enc, filas = hoja_alertas(res.reporte)
    assert filas[0][enc.index("Resultado")] == "NO VERIFICADO"
    assert filas[0][enc.index("Motivo")] == "sin resultados"
    assert (res.total, res.exitosas, res.fallidas) == (1, 0, 1)
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'consultor.main'`.

- [ ] **Step 3: Implementar**

`consultor/main.py`:
```python
import argparse
import tomllib
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .comparator import comparar
from .fetcher import Fetcher
from .loader import crear_fuente
from .models import FALLIDA, NO_VERIFICADO, Consulta, Veredicto
from .reporter import LEYENDA, avisar, escribir_reporte, leer_decisiones
from .store import Store

# R5 se evalúa solo después de esta cantidad de consultas, para que dos fallos
# seguidos al inicio no detengan un ciclo de 44 radicados.
MIN_MUESTRA = 10
MOTIVO_DETENIDO = "ciclo detenido: fuente no disponible"


@dataclass
class Resumen:
    ciclo_id: int
    total: int
    exitosas: int
    fallidas: int
    novedades: int
    estado: str
    reporte: Path


def correr_ciclo(
    radicados, fetcher, store, carpeta_reportes, validador, max_fallas, avisar_fn, ahora=datetime.now
) -> Resumen:
    for alerta_id, decision, usuario in leer_decisiones(carpeta_reportes, avisar_fn):
        store.registrar_decision(alerta_id, decision, usuario or validador, ahora())

    ciclo_id = store.iniciar_ciclo(ahora())
    consultados = fallas = 0
    detenido = False
    ultimo = len(radicados) - 1
    for i, r in enumerate(radicados):
        store.registrar_radicado(r)
        if store.ya_consultado(ciclo_id, r.radicado):
            continue
        if detenido:
            store.registrar_resultado(
                ciclo_id,
                r.radicado,
                Consulta(FALLIDA, motivo=MOTIVO_DETENIDO),
                Veredicto(NO_VERIFICADO, motivo=MOTIVO_DETENIDO),
                "",
                ahora(),
            )
            continue
        consulta = fetcher.consultar(r)
        veredicto = comparar(
            consulta, store.ids_conocidos(r.radicado), store.tiene_referencia(r.radicado)
        )
        store.registrar_resultado(
            ciclo_id, r.radicado, consulta, veredicto, store.ultima_actuacion(r.radicado), ahora()
        )
        consultados += 1
        fallas += consulta.falla_portal
        if consultados >= MIN_MUESTRA and fallas / consultados > max_fallas:  # R5
            detenido = True
            avisar_fn(
                f"Fuente no disponible: fallaron {fallas} de {consultados} consultas. "
                "Ciclo detenido, activar consulta manual."
            )
        elif i < ultimo:
            fetcher.pausar()

    estado = "Detenido: fuente no disponible" if detenido else "Completo"
    store.cerrar_ciclo(ciclo_id, estado, ahora())
    res = store.resumen(ciclo_id)
    ruta = escribir_reporte(
        store.filas_reporte(ciclo_id), {**res, "estado": estado}, carpeta_reportes, ciclo_id, ahora()
    )
    avisar_fn(
        f"Ciclo {ciclo_id}: {res['total']} consultados, {res['exitosas']} exitosos, "
        f"{res['fallidas']} fallidos, {res['novedades']} posibles novedades. "
        f"Reporte: {ruta}. {LEYENDA}"
    )
    return Resumen(ciclo_id, res["total"], res["exitosas"], res["fallidas"], res["novedades"], estado, ruta)


def cargar_config(ruta) -> dict:
    with open(ruta, "rb") as f:
        return tomllib.load(f)


def ejecutar(argv=None) -> int:
    """0 = ciclo completo, 1 = detenido por R5, 2 = error inesperado."""
    p = argparse.ArgumentParser(prog="consultor")
    p.add_argument("comando", choices=["run"])
    p.add_argument("--config", default="config.toml")
    p.add_argument("--solo-radicado", help="consulta un único radicado, para pruebas")
    args = p.parse_args(argv)

    cfg = cargar_config(args.config)
    carpeta = Path(cfg["salida"]["carpeta_reportes"])
    log = carpeta / "avisos.log"

    def avisar_fn(texto):
        avisar(texto, log, datetime.now())

    try:
        radicados = crear_fuente(cfg["fuente"]).cargar()
        if args.solo_radicado:
            radicados = [r for r in radicados if r.radicado == args.solo_radicado]
        portal = cfg["portal"]
        fetcher = Fetcher(
            pausa=portal["pausa_segundos"],
            reintentos=portal["reintentos"],
            espera=portal["espera_segundos"],
            timeout=portal["timeout_segundos"],
        )
        res = correr_ciclo(
            radicados,
            fetcher,
            Store(cfg["salida"]["base_datos"]),
            carpeta,
            cfg["salida"]["validador"],
            portal["max_fallas_ciclo"],
            avisar_fn,
        )
    except Exception:  # CA4: un error inesperado nunca deja el ciclo parado en silencio
        avisar_fn("El ciclo terminó con un error inesperado:\n" + traceback.format_exc())
        return 2
    return 0 if res.estado == "Completo" else 1
```

`consultor/__main__.py`:
```python
import sys

from .main import ejecutar

if __name__ == "__main__":
    sys.exit(ejecutar(sys.argv[1:]))
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_main.py -v`
Expected: 5 passed.

- [ ] **Step 5: Correr toda la suite**

Run: `python -m pytest -v`
Expected: todas pasan (6 + 9 + 11 + 7 + 8 + 5 = 46 passed).

- [ ] **Step 6: Commit**

```bash
git add consultor/main.py consultor/__main__.py tests/test_main.py
git commit -m "feat: ciclo completo con R5, reanudación y línea de comandos" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: configuración, script de ejecución y README

**Files:**
- Create: `config.example.toml`, `scripts/ejecutar_ciclo.bat`, `README.md`

- [ ] **Step 1: Crear `config.example.toml`**

```toml
[fuente]
tipo = "excel"
ruta = "C:/consultor_judicial/entrada/extracto_procesos.xlsx"
hoja = "GENERAL"
col_radicado = "Radicado"
col_empresa = "Empresa"
col_despacho = "Despacho"
col_calidad = "Calidad"
col_estado = "Estado"
estados_incluidos = []

[salida]
base_datos = "datos/consultor.db"
carpeta_reportes = "reportes"
validador = "Alisson Rengifo"

[portal]
pausa_segundos = 1.0
reintentos = 3
espera_segundos = 2.0
timeout_segundos = 30
max_fallas_ciclo = 0.5
```

- [ ] **Step 2: Crear `scripts/ejecutar_ciclo.bat`**

```bat
@echo off
cd /d "%~dp0.."
if not exist reportes mkdir reportes
call .venv\Scripts\activate.bat
python -m consultor run --config config.toml >> reportes\consola.log 2>&1
exit /b %ERRORLEVEL%
```

- [ ] **Step 3: Crear `README.md`**

````markdown
# Consultor Judicial

Consulta los radicados de la lista en la API de la Rama Judicial, detecta actuaciones nuevas y deja un Excel de alertas para que Alisson Rengifo las valide. No decide nada jurídico y no escribe en el cuadro oficial.

## Instalación

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy config.example.toml config.toml
```

Edita `config.toml`: ruta del Excel con los radicados y nombres de sus columnas.

## Uso

```
python -m consultor run
python -m consultor run --solo-radicado 11001400307720210114700
```

Códigos de salida: 0 ciclo completo, 1 detenido por fuente no disponible, 2 error inesperado.

## Validación

Abrir `reportes\reporte_ciclo_NNNN_AAAA-MM-DD.xlsx`, hoja Alertas. En cada fila con ID de alerta elegir en la columna Decisión: Confirmada o Descartada (y escribir el nombre en Validó). Guardar y cerrar el archivo. El ciclo siguiente lee la decisión.

## Programación (la configura Sistemas)

```
schtasks /Create /TN "ConsultorJudicial" /TR "C:\consultor_judicial\scripts\ejecutar_ciclo.bat" /SC WEEKLY /D MON,WED,FRI /ST 06:30 /RU DOMINIO\cuenta_servicio /RP *
```

La cuenta debe tener permiso de lectura sobre el Excel de radicados y de escritura sobre `datos\` y `reportes\`.

## Pruebas

```
python -m pytest
```
````

- [ ] **Step 4: Verificar que la suite sigue verde**

Run: `python -m pytest -q`
Expected: 46 passed.

- [ ] **Step 5: Commit**

```bash
git add config.example.toml scripts README.md
git commit -m "docs: configuración de ejemplo, script de ejecución y README" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: prueba de humo contra el portal real

Esta tarea valida CA1 de forma manual. No automatiza nada.

**Files:** ninguno nuevo. Crea `config.toml` y un Excel de prueba locales (ambos fuera de git).

- [ ] **Step 1: Crear un Excel de prueba**

Crear `entrada\prueba.xlsx` con una hoja `GENERAL` y las columnas `Radicado`, `Empresa`, `Despacho`, `Calidad`, `Estado`, con 3 a 5 radicados reales del cuadro de seguimiento (públicos), más uno inválido (`123`) y uno inexistente (`11001400000020200000000`).

- [ ] **Step 2: Crear `config.toml`**

Copiar `config.example.toml` a `config.toml` y poner `ruta = "entrada/prueba.xlsx"`.

- [ ] **Step 3: Ejecutar el primer ciclo**

Run: `python -m consultor run`
Expected: imprime `Ciclo 1: 6 consultados, ... exitosos, ... fallidos, 0 posibles novedades`. Los radicados reales son SIN CAMBIO (referencia inicial), el inválido y el inexistente son NO VERIFICADO con motivo. Código de salida 0.

- [ ] **Step 4: Revisar el Excel**

Abrir `reportes\reporte_ciclo_0001_*.xlsx`. Verificar: hoja Resumen con la leyenda, hoja Alertas con los dos NO VERIFICADO y sus motivos, hoja Sin cambio con los reales, y que no aparece ningún nombre de parte.

- [ ] **Step 5: Simular una novedad**

Con `sqlite3` o un script, borrar la actuación más reciente de un radicado:
```
python -c "import sqlite3; c=sqlite3.connect('datos/consultor.db'); c.execute('DELETE FROM actuacion WHERE id_reg_actuacion = (SELECT id_reg_actuacion FROM actuacion ORDER BY fecha_actuacion DESC, id_reg_actuacion DESC LIMIT 1)'); c.commit()"
```
Run: `python -m consultor run`
Expected: ese radicado sale como POSIBLE NOVEDAD con la actuación borrada como "detectada". Es el único caso que simula un movimiento real.

- [ ] **Step 6: Marcar y repetir**

Marcar Descartada en esa fila, guardar y cerrar el Excel. Run: `python -m consultor run`
Expected: 0 novedades, y la alerta queda Descartada con "Alisson Rengifo" como validador.

- [ ] **Step 7: Medir el tiempo**

Anotar cuánto tardó el ciclo con N radicados para estimar el de 44 y el de 500.

- [ ] **Step 8: Commit del estado final**

```bash
git status --short
```
Expected: sin cambios pendientes (config.toml, datos y reportes están ignorados).

---

## Autorrevisión

**Cobertura de la spec** (secciones del documento de diseño):
- Loader intercambiable: Task 4 (contrato `cargar()` + `crear_fuente`).
- Fetcher, 3 llamadas, `SoloActivos=false`, 404 como sin actuaciones, descarte de datos personales: Task 3.
- R1, R2: Task 1. R3, R4, R7: Task 3 y Task 4. R5: Task 6. R6, R8: Task 2. R9: loader solo lectura, ninguna escritura fuera de `datos/` y `reportes/`.
- Reporte en tres hojas, leyenda, orden y desplegable de Decisión: Task 5.
- `registrar_decision` como puerta única: Task 2. Importación desde el Excel: Tasks 5 y 6.
- Ciclo reanudable: Tasks 2 y 6. Transacción por radicado: Task 2.
- Aviso: Task 5 (`avisar` escribe a log y consola). El canal real queda pendiente con Sistemas.
- CA1 y CA2 contra datos reales: Task 8. CA3 a CA5: pruebas automáticas.

**Desviaciones respecto a la spec, a conocer:**
- El reporte tiene una fila por actuación nueva, no una por radicado, porque la decisión de Alisson es por alerta.
- El enlace del reporte apunta a la página de búsqueda del portal, no al proceso. No verifiqué la URL de detalle y no la invento.
- El número de reintentos y el porcentaje de fallas son valores de `config.toml` (3 y 0.5), a confirmar con Sistemas.

**Consistencia de tipos:** `Consulta`, `Veredicto`, `Radicado` y `Actuacion` se definen en Task 0 y se usan con los mismos campos en las demás. `registrar_resultado(ciclo_id, radicado, consulta, veredicto, anterior, ahora)` se define en Task 2 y se llama igual en Task 6. `escribir_reporte(filas, resumen, carpeta, ciclo_id, ahora)` coincide entre Tasks 5 y 6.
