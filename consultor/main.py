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
    reporte: Path | None


def correr_ciclo(
    radicados, fetcher, store, carpeta_reportes, validador, max_fallas, avisar_fn, ahora=datetime.now
) -> Resumen:
    if not radicados:
        avisar_fn(
            "La lista de radicados está vacía. No se consultó nada: "
            "revisar la fuente y los filtros de estado."
        )
        return Resumen(0, 0, 0, 0, 0, "Lista vacía", None)
    for alerta_id, decision, usuario in leer_decisiones(carpeta_reportes, avisar_fn):
        store.registrar_decision(alerta_id, decision, usuario or validador, ahora())

    interrumpidos = store.cerrar_interrumpidos(ahora())
    if interrumpidos:
        avisar_fn(f"{interrumpidos} ciclo(s) anterior(es) quedaron interrumpido(s). Sus alertas pendientes siguen en el reporte.")
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
    res = store.resumen(ciclo_id)
    ruta = escribir_reporte(
        store.filas_reporte(ciclo_id), {**res, "estado": estado}, carpeta_reportes, ciclo_id, ahora()
    )
    store.cerrar_ciclo(ciclo_id, estado, ahora())
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
