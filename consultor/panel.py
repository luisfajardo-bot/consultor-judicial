"""Lógica de la pantalla, sin tkinter: la vista (ventana.py) solo pinta lo que esto decide."""

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .bloqueo import ciclo_en_curso
from .models import CONFIRMADA

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
    if not ciclo_en_curso(carpeta_datos):  # sin candado, estado.txt es un resto viejo
        return None
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


def solicitar_cancelacion(carpeta_datos) -> bool:
    """Pide al ciclo en marcha que se detenga. False si no hay ninguno corriendo."""
    if not ciclo_en_curso(carpeta_datos):
        return False
    (Path(carpeta_datos) / "cancelar.txt").write_text(f"{datetime.now():%H:%M:%S}", encoding="utf-8")
    return True


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


@dataclass(frozen=True)
class ConfigAlertas:
    exigir: bool = False
    umbral: int = 30
    objetivo: int = 10
    dias_corte: int = 7


def config_alertas(cfg: dict) -> ConfigAlertas:
    a = cfg.get("alertas", {})
    base = ConfigAlertas()
    return ConfigAlertas(
        exigir=a.get("exigir_puesta_al_dia", base.exigir),
        umbral=a.get("umbral_anteriores", base.umbral),
        objetivo=a.get("objetivo_anteriores", base.objetivo),
        dias_corte=a.get("dias_corte_regla", base.dias_corte),
    )


def separar(pendientes: list[dict], hoy: date, dias: int) -> tuple[list[dict], list[dict]]:
    desde = hoy - timedelta(days=dias)
    en_rango, anteriores = [], []
    for p in pendientes:
        (en_rango if date.fromisoformat(p["detectada"][:10]) >= desde else anteriores).append(p)
    return en_rango, anteriores


def contar_para_regla(pendientes: list[dict], hoy: date, c: ConfigAlertas) -> int:
    return len(separar(pendientes, hoy, c.dias_corte)[1])


def evaluar_obligacion(activa: bool, anteriores: int, c: ConfigAlertas) -> bool:
    if not c.exigir:
        return False
    if anteriores > c.umbral:
        return True
    if anteriores < c.objetivo:
        return False
    return activa


@dataclass(frozen=True)
class AccionCierre:
    tipo: str  # "bloquear", "preguntar" o "cerrar"
    texto: str = ""


def accion_al_cerrar(
    obligacion: bool, anteriores_regla: int, en_rango: int, dias: int, c: ConfigAlertas
) -> AccionCierre:
    if obligacion:
        return AccionCierre("bloquear", texto_obligacion(anteriores_regla, c))
    if en_rango > 0:
        return AccionCierre(
            "preguntar",
            f"Quedan {en_rango} alertas por decidir de los últimos {dias} días. ¿Cerrar de todas formas?",
        )
    return AccionCierre("cerrar")


def texto_pestana_rango(dias: int, n: int) -> str:
    if dias == 0:
        return f"Por decidir · hoy ({n})"
    return f"Por decidir · últimos {dias} días ({n})"


def texto_pestana_anteriores(n: int) -> str:
    return f"Anteriores sin decidir ({n})"


def texto_obligacion(n: int, c: ConfigAlertas) -> str:
    return (
        f"Hay {n} alertas anteriores sin decidir (detectadas hace más de {c.dias_corte} días). "
        f"Deben quedar menos de {c.objetivo} antes de cerrar. Faltan {n - c.objetivo + 1}."
    )


def texto_dias_guardado(dias: int) -> str:
    if dias == 0:
        return (
            "Guardado: 0 días. No se avisará nada en radicados nuevos; "
            "Por decidir muestra solo lo detectado hoy."
        )
    return (
        f"Guardado: {dias} días. La pestaña Por decidir ya muestra los últimos {dias} días; "
        "en radicados nuevos rige desde la próxima consulta."
    )


def texto_confirmar_bloque(estado: str, n: int) -> str:
    verbo = "Confirmar" if estado == CONFIRMADA else "Descartar"
    return f"¿{verbo} {n} alertas? Se puede corregir desde Ver decididas."
