import argparse
import os
import sys
import tomllib
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .bloqueo import Bloqueo, CicloEnCurso
from .comparator import comparar
from .consola import barra
from .fetcher import Fetcher
from .loader import crear_fuente
from .models import ERROR, FALLIDA, NO_VERIFICADO, Consulta, Veredicto
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
    radicados, fetcher, store, carpeta_reportes, validador, max_fallas, avisar_fn, ahora=datetime.now, progreso=None, parcial=False
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
    ciclo_id = store.iniciar_ciclo(ahora(), parcial)
    consultados = fallas = cambios_api = 0
    detenido = False
    ultimo = len(radicados) - 1
    store.registrar_radicados(radicados)
    for i, r in enumerate(radicados):
        if store.ya_consultado(ciclo_id, r.radicado):
            pass
        elif detenido:
            store.registrar_resultado(
                ciclo_id,
                r.radicado,
                Consulta(FALLIDA, motivo=MOTIVO_DETENIDO),
                Veredicto(NO_VERIFICADO, motivo=MOTIVO_DETENIDO),
                "",
                ahora(),
            )
        else:
            consulta = fetcher.consultar(r)
            veredicto = comparar(
                consulta, store.ids_conocidos(r.radicado), store.tiene_referencia(r.radicado)
            )
            store.registrar_resultado(
                ciclo_id, r.radicado, consulta, veredicto, store.ultima_actuacion(r.radicado), ahora()
            )
            consultados += 1
            fallas += consulta.falla_portal
            cambios_api += consulta.estado == ERROR
            if consultados >= MIN_MUESTRA and fallas / consultados > max_fallas:  # R5
                detenido = True
                avisar_fn(
                    f"Fuente no disponible: fallaron {fallas} de {consultados} consultas. "
                    "Ciclo detenido, activar consulta manual."
                )
            elif i < ultimo:
                fetcher.pausar()
        if progreso:
            progreso(i + 1, len(radicados), r.radicado)

    fuente_caida = consultados > 0 and fallas / consultados > max_fallas
    if cambios_api:
        avisar_fn(
            f"ALERTA: la API de la Rama Judicial posiblemente cambió. {cambios_api} de {consultados} "
            "consultas devolvieron una respuesta con una forma inesperada. "
            "Revisar la herramienta y usar la consulta manual mientras tanto."
        )
    if detenido and cambios_api:
        estado = "Detenido: posible cambio en la API"
    elif detenido:
        estado = "Detenido: fuente no disponible"
    elif cambios_api:
        estado = "Completo con alerta: posible cambio en la API"
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
    """0 = ciclo completo, 1 = detenido o con fallas, 2 = error inesperado, 3 = no se ejecutó (candado o límite)."""
    p = argparse.ArgumentParser(prog="consultor")
    p.add_argument("comando", choices=["run"])
    p.add_argument("--config", default="config.toml")
    p.add_argument("--solo-radicado", help="consulta un único radicado, para pruebas")
    p.add_argument("--forzar", action="store_true", help="salta el límite entre ejecuciones (no el candado)")
    p.add_argument("--abrir", action="store_true", help="abre el Excel al terminar")
    args = p.parse_args(argv)

    cfg = cargar_config(args.config)
    carpeta = Path(cfg["salida"]["carpeta_reportes"])
    log = carpeta / "avisos.log"
    barra_activa = False

    def avisar_fn(texto):
        nonlocal barra_activa
        if barra_activa:
            print()
            barra_activa = False
        avisar(texto, log, datetime.now())

    minimo = cfg.get("ejecucion", {}).get("min_minutos_entre_ciclos", 30)
    try:
        with Bloqueo(Path(cfg["salida"]["base_datos"]).parent) as bloqueo:
            store = Store(cfg["salida"]["base_datos"])
            ultimo = store.ultimo_cierre()
            if not (args.forzar or args.solo_radicado) and ultimo:
                hasta = ultimo + timedelta(minutes=minimo)
                ahora = datetime.now()
                if ahora < hasta:
                    avisar_fn(
                        f"La última consulta terminó hace {int((ahora - ultimo).total_seconds() // 60)} min "
                        f"(a las {ultimo:%H:%M}). Para no repetir consultas al portal, espera hasta las "
                        f"{hasta:%H:%M}, o pide a quien administra la herramienta que use --forzar."
                    )
                    return 3
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
            consola = sys.stdout.isatty()
            if consola:
                print(f"Consultando {len(radicados)} procesos en la Rama Judicial. No cierres esta ventana.")

            def progreso(hecho, total, radicado):
                nonlocal barra_activa
                bloqueo.publicar(f"{datetime.now():%H:%M} | {hecho} de {total}")
                if consola:
                    print("\r" + barra(hecho, total) + f" {radicado}", end="", flush=True)
                    barra_activa = True

            res = correr_ciclo(
                radicados,
                fetcher,
                store,
                carpeta,
                cfg["salida"]["validador"],
                portal["max_fallas_ciclo"],
                avisar_fn,
                progreso=progreso,
                parcial=bool(args.solo_radicado),
            )
            if barra_activa:
                print()
                barra_activa = False
    except CicloEnCurso as e:
        avisar_fn(
            "Ya hay una consulta en curso"
            + (f" ({e.estado})" if e.estado else "")
            + ". No hace falta lanzarla otra vez: espera a que termine."
        )
        return 3
    except Exception:  # CA4: un error inesperado nunca deja el ciclo parado en silencio
        avisar_fn("El ciclo terminó con un error inesperado:\n" + traceback.format_exc())
        return 2
    if args.abrir and res.reporte and hasattr(os, "startfile"):
        os.startfile(res.reporte)
    return 0 if res.estado == "Completo" else 1
