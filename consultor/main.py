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
from .reporter import LEYENDA, escribir_reporte, leer_decisiones
from .store import Store

# R5 se evalúa solo después de esta cantidad de consultas, para que dos fallos
# seguidos al inicio no detengan un ciclo de 44 radicados.
MIN_MUESTRA = 10
MOTIVO_DETENIDO = "ciclo detenido: fuente no disponible"
ESTADO_PAUSADO = "Pausado: el portal bloqueó las consultas"


@dataclass
class Resumen:
    ciclo_id: int
    total: int
    exitosas: int
    fallidas: int
    novedades: int
    estado: str
    reporte: Path | None
    pendientes: int = 0


def correr_ciclo(
    radicados, fetcher, store, carpeta_reportes, validador, max_fallas, avisar_fn, ahora=datetime.now, progreso=None, parcial=False, min_minutos=30
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
    detenido = bloqueado = False
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
            if consulta.bloqueo:  # no se registra: se reintenta al reanudar
                bloqueado = True
                pendientes = store.pendientes(ciclo_id, len(radicados))
                avisar_fn(
                    "ALERTA: el portal bloqueó las consultas (HTTP 403 o 429) después de "
                    f"{len(radicados) - pendientes} radicados. Quedan {pendientes} sin consultar. "
                    "La próxima ejecución continuará desde ahí; "
                    f"espere al menos {min_minutos} minutos."
                )
                break
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
    if bloqueado:
        estado = ESTADO_PAUSADO
    elif detenido and cambios_api:
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
    pendientes = store.pendientes(ciclo_id, len(radicados)) if bloqueado else 0
    ruta = escribir_reporte(
        store.filas_reporte(ciclo_id),
        {**res, "estado": estado, "pendientes": pendientes},
        carpeta_reportes,
        ciclo_id,
        ahora(),
    )
    store.cerrar_ciclo(ciclo_id, estado, ahora())
    avisar_fn(
        f"Ciclo {ciclo_id}: {res['total']} consultados, {res['exitosas']} exitosos, "
        f"{res['fallidas']} fallidos, {res['novedades']} posibles novedades. "
        f"Reporte: {ruta}. {LEYENDA}"
    )
    return Resumen(ciclo_id, res["total"], res["exitosas"], res["fallidas"], res["novedades"], estado, ruta, pendientes)


def cargar_config(ruta) -> dict:
    with open(ruta, "rb") as f:
        return tomllib.load(f)


@dataclass
class Ejecucion:
    codigo: int
    mensaje: str
    resumen: Resumen | None


def _registrar(texto, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")


def ejecutar_ciclo(cfg, *, forzar=False, solo_radicado=None, progreso=None, avisar_fn=None) -> Ejecucion:
    """Un ciclo con candado, límite entre ejecuciones y avance publicado. No imprime.

    codigo: 0 = completo, 1 = detenido o con fallas, 2 = error inesperado, 3 = no se ejecutó (candado o límite).
    """
    carpeta = Path(cfg["salida"]["carpeta_reportes"])
    log = carpeta / "avisos.log"

    def aviso(texto):
        _registrar(texto, log)
        if avisar_fn:
            avisar_fn(texto)

    minimo = cfg.get("ejecucion", {}).get("min_minutos_entre_ciclos", 30)
    inicio = datetime.now()
    try:
        with Bloqueo(Path(cfg["salida"]["base_datos"]).parent) as bloqueo:
            store = Store(cfg["salida"]["base_datos"])
            ultimo = store.ultimo_cierre()
            if not (forzar or solo_radicado) and ultimo:
                hasta = ultimo + timedelta(minutes=minimo)
                ahora = datetime.now()
                if ahora < hasta:
                    msg = (
                        f"La última consulta terminó hace {int((ahora - ultimo).total_seconds() // 60)} min "
                        f"(a las {ultimo:%H:%M}). Para no repetir consultas al portal, espera hasta las "
                        f"{hasta:%H:%M}, o pide a quien administra la herramienta que use --forzar."
                    )
                    aviso(msg)
                    return Ejecucion(3, msg, None)
            radicados = crear_fuente(cfg["fuente"]).cargar()
            if solo_radicado:
                radicados = [r for r in radicados if r.radicado == solo_radicado]
            portal = cfg["portal"]
            fetcher = Fetcher(
                pausa=portal["pausa_segundos"],
                reintentos=portal["reintentos"],
                espera=portal["espera_segundos"],
                timeout=portal["timeout_segundos"],
                pausa_peticiones=portal.get("pausa_peticiones_segundos", 1.5),
                consultar_detalle=portal.get("consultar_detalle", False),
                reintentos_bloqueo=portal.get("reintentos_bloqueo", 3),
                espera_bloqueo=portal.get("espera_bloqueo_segundos", 60),
            )

            def avance(hecho, total, radicado):
                bloqueo.publicar(f"{inicio:%H:%M} | {hecho} de {total}")
                if progreso:
                    progreso(hecho, total, radicado)

            res = correr_ciclo(
                radicados,
                fetcher,
                store,
                carpeta,
                cfg["salida"]["validador"],
                portal["max_fallas_ciclo"],
                aviso,
                progreso=avance,
                parcial=bool(solo_radicado),
                min_minutos=minimo,
            )
    except CicloEnCurso as e:
        msg = (
            "Ya hay una consulta en curso"
            + (f" ({e.estado})" if e.estado else "")
            + ". No hace falta lanzarla otra vez: espera a que termine."
        )
        aviso(msg)
        return Ejecucion(3, msg, None)
    except Exception:  # CA4: un error inesperado nunca deja el ciclo parado en silencio
        msg = "El ciclo terminó con un error inesperado:\n" + traceback.format_exc()
        aviso(msg)
        return Ejecucion(2, msg, None)
    return Ejecucion(0 if res.estado == "Completo" else 1, "", res)


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
    consola = sys.stdout.isatty()
    barra_activa = False

    def cerrar_barra():
        nonlocal barra_activa
        if barra_activa:
            print()
            barra_activa = False

    def avisar_fn(texto):
        cerrar_barra()
        print(texto)

    def progreso(hecho, total, radicado):
        nonlocal barra_activa
        if not consola:
            return
        if hecho == 1:
            print(f"Consultando {total} procesos en la Rama Judicial. No cierres esta ventana.")
        print("\r" + barra(hecho, total) + f" {radicado}", end="", flush=True)
        barra_activa = True

    e = ejecutar_ciclo(
        cfg, forzar=args.forzar, solo_radicado=args.solo_radicado, progreso=progreso, avisar_fn=avisar_fn
    )
    cerrar_barra()
    if args.abrir and e.resumen and e.resumen.reporte and hasattr(os, "startfile"):
        os.startfile(e.resumen.reporte)
    return e.codigo
