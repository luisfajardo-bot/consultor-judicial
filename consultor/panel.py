"""Lógica de la pantalla, sin tkinter: la vista (ventana.py) solo pinta lo que esto decide."""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ESTADO_RE = re.compile(r"(\d{1,2}:\d{2})\s*\|\s*(\d+) de (\d+)")
SIN_AVANCE_SEG = 90


@dataclass(frozen=True)
class Avance:
    hecho: int
    total: int
    segundos_sin_avance: float
    hora_inicio: str


@dataclass(frozen=True)
class ResumenCiclo:
    id: int
    fin: datetime
    estado: str
    total: int
    exitosas: int
    fallidas: int
    novedades: int
    pendientes_validar: int


def leer_avance(carpeta_datos, ahora=None) -> Avance | None:
    ruta = Path(carpeta_datos) / "estado.txt"
    try:
        texto = ruta.read_text(encoding="utf-8")
        modificado = ruta.stat().st_mtime
    except OSError:
        return None
    m = ESTADO_RE.search(texto)
    if not m:
        return None
    ahora = time.time() if ahora is None else ahora
    return Avance(int(m.group(2)), int(m.group(3)), max(0.0, ahora - modificado), m.group(1))


def resumen_ultimo_ciclo(store) -> ResumenCiclo | None:
    c = store.ultimo_ciclo()
    if c is None:
        return None
    r = store.resumen(c["id"])
    return ResumenCiclo(
        c["id"], c["fin"], c["estado"], r["total"], r["exitosas"], r["fallidas"],
        r["novedades"], store.contar_pendientes(),
    )


def ultimo_reporte(carpeta) -> Path | None:
    nombres = sorted(
        p for p in Path(carpeta).glob("reporte_ciclo_*.xlsx") if not p.name.startswith("~$")
    )
    return nombres[-1] if nombres else None


def texto_resumen(r: ResumenCiclo | None) -> str:
    if r is None:
        return "Todavía no se ha hecho ninguna consulta."
    return (
        f"Última consulta: {r.fin:%Y-%m-%d %H:%M} ({r.estado})\n"
        f"{r.total} consultados, {r.exitosas} exitosos, {r.fallidas} sin verificar, "
        f"{r.novedades} posibles novedades, {r.pendientes_validar} alertas por validar"
    )


def texto_avance(a: Avance) -> str:
    t = f"Consultando: {a.hecho} de {a.total} (desde las {a.hora_inicio})"
    if a.segundos_sin_avance > SIN_AVANCE_SEG:
        t += f" Sin avance hace {int(a.segundos_sin_avance // 60)} min: el portal puede estar pidiendo esperar."
    return t
