import argparse
import os
import sys
import tomllib
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .ajustes import DIAS_POR_DEFECTO, consultas_activas, leer_dias
from .bloqueo import Bloqueo, CicloEnCurso
from .comparator import comparar
from .consola import barra
from .fetcher import CicloCancelado, Fetcher
from .loader import crear_fuente
from .mantenimiento import archivar_reportes, borrar_archivo_antiguo, respaldar_base
from .models import ERROR, FALLIDA, NO_VERIFICADO, Consulta, Veredicto
from .reporter import LEYENDA, escribir_reporte, leer_decisiones
from .store import EXCEL_APLICADA, EXCEL_IGNORADA, Store

# R5 se evalúa solo después de esta cantidad de consultas, para que dos fallos
# seguidos al inicio no detengan un ciclo de 44 radicados.
MIN_MUESTRA = 10
# Una caída a mitad de ciclo se reconoce por fallas seguidas, aunque R5 (que mira todo el ciclo) no llegue.
FALLAS_SEGUIDAS = 5
# Ante una caída el ciclo espera y reintenta lo fallido antes de pausarse. La del 14-oct duró ~35 min.
ESPERAS_CAIDA = (900, 1800)
# Fallas sueltas (sin caída declarada) se reintentan una vez al final: el 17-nov fallaron 12 de 77 y
# minutos después respondían bien.
ESPERA_REPASO = 300
MOTIVO_DETENIDO = "ciclo detenido: fuente no disponible"
ESTADO_CANCELADO = "Cancelado por el usuario"
ESTADO_PAUSADO = "Pausado: el portal bloqueó las consultas"
ESTADO_SIN_RESPUESTA = "Pausado: el portal no responde"
PROTOCOLO = (
    "Vuelva a intentar en 1 hora: seguirá desde donde quedó. "
    "Si vuelve a fallar, haga hoy la consulta manual y avise a quien administra la herramienta."
)


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


def _desde(primer_intento, ahora: datetime, dias: int) -> str:
    """Corte de la primera consulta exitosa, anclado al primer intento del radicado: si estuvo
    fallando varios días, lo registrado desde que entró a la lista sigue contando."""
    if dias <= 0:
        return ""
    return ((primer_intento or ahora) - timedelta(days=dias)).date().isoformat()


def correr_ciclo(
    radicados, fetcher, store, carpeta_reportes, validador, max_fallas, avisar_fn, ahora=datetime.now, progreso=None, parcial=False, cancelado=None, alertar_primera_dias=0
) -> Resumen:
    if not radicados:
        avisar_fn(
            "La lista de radicados está vacía. No se consultó nada: "
            "revisar la fuente y los filtros de estado."
        )
        return Resumen(0, 0, 0, 0, 0, "Lista vacía", None)
    resultados = [
        store.registrar_decision(alerta_id, decision, usuario or validador, ahora(), fecha)
        for alerta_id, decision, usuario, fecha in leer_decisiones(carpeta_reportes, avisar_fn)
    ]
    aplicadas = resultados.count(EXCEL_APLICADA)
    ignoradas = resultados.count(EXCEL_IGNORADA)
    if aplicadas:
        avisar_fn(f"Se registraron {aplicadas} decisión(es) tomadas en los reportes.")
    if ignoradas:
        avisar_fn(
            f"{ignoradas} decisión(es) de reportes anteriores se ignoraron "
            "porque la alerta se decidió después en la ventana."
        )

    interrumpidos = store.cerrar_interrumpidos(ahora())
    if interrumpidos:
        avisar_fn(f"{interrumpidos} ciclo(s) anterior(es) quedaron interrumpido(s). Sus alertas pendientes siguen en el reporte.")
    ciclo_id = store.iniciar_ciclo(ahora(), parcial)
    consultados = fallas = cambios_api = no_hallados = seguidas = 0
    detenido = bloqueado = cancelo = sin_respuesta = False
    ultimo = len(radicados) - 1
    caidas = 0
    por_radicado: dict[str, Consulta] = {}  # último resultado de cada radicado en esta corrida: da el estado final
    solo = None  # en el repaso final, los únicos radicados que se vuelven a consultar
    store.registrar_radicados(radicados)

    def avisar_cancelado():
        pendientes = store.pendientes(ciclo_id, len(radicados))
        avisar_fn(
            f"Consulta cancelada por el usuario después de {len(radicados) - pendientes} radicados. "
            f"Quedan {pendientes} sin consultar. Puede continuar más tarde y seguirá desde ahí."
        )

    i = 0
    while True:
        if i >= len(radicados):  # fin de la pasada: repaso final de las fallas del portal, una sola vez
            if solo is not None or cancelo or bloqueado or sin_respuesta or detenido:
                break
            solo = {x for x, c in por_radicado.items() if c.falla_portal and c.estado == FALLIDA}
            if not solo:
                break
            avisar_fn(
                f"{len(solo)} radicado(s) fallaron por el portal. "
                f"Se reintentan una vez en {ESPERA_REPASO // 60} min."
            )
            try:
                fetcher.esperar(ESPERA_REPASO)
            except CicloCancelado:
                cancelo = True
                avisar_cancelado()
                break
            i = consultados = fallas = cambios_api = no_hallados = seguidas = 0
            continue
        r = radicados[i]
        i += 1
        if cancelado and cancelado():
            cancelo = True
            avisar_cancelado()
            break
        if store.ya_consultado(ciclo_id, r.radicado) or (solo is not None and r.radicado not in solo):
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
            try:
                consulta = fetcher.consultar(r)
            except CicloCancelado:  # el radicado en vuelo no se registra: se consulta al reanudar
                cancelo = True
                avisar_cancelado()
                break
            if consulta.bloqueo:  # no se registra: se reintenta al reanudar
                bloqueado = True
                pendientes = store.pendientes(ciclo_id, len(radicados))
                avisar_fn(
                    "ALERTA: el portal bloqueó las consultas (HTTP 403 o 429) después de "
                    f"{len(radicados) - pendientes} radicados. Quedan {pendientes} sin consultar. "
                    f"{PROTOCOLO}"
                )
                break
            desde = _desde(store.primer_intento(r.radicado), ahora(), alertar_primera_dias)
            veredicto = comparar(
                consulta,
                store.ids_vistos(r.radicado, (a.id_reg_actuacion for a in consulta.actuaciones)),
                store.tiene_referencia(r.radicado),
                desde,
            )
            store.registrar_resultado(
                ciclo_id, r.radicado, consulta, veredicto, store.ultima_actuacion(r.radicado), ahora()
            )
            por_radicado[r.radicado] = consulta
            consultados += 1
            fallas += consulta.falla_portal
            seguidas = seguidas + 1 if consulta.falla_portal else 0
            cambios_api += consulta.estado == ERROR
            no_hallados += consulta.no_hallado
            r5 = consultados >= MIN_MUESTRA and fallas / consultados > max_fallas
            api_rota = cambios_api * 2 > fallas  # un ERROR suelto en plena caída no apaga la espera
            if (r5 or seguidas >= FALLAS_SEGUIDAS) and not api_rota:  # un cambio de la API no se arregla esperando
                if caidas < len(ESPERAS_CAIDA):
                    espera = ESPERAS_CAIDA[caidas]
                    caidas += 1
                    avisar_fn(
                        f"El portal no responde: fallaron {fallas} de {consultados} consultas. "
                        f"Esperando {espera // 60} min para reintentar ({caidas} de {len(ESPERAS_CAIDA)})."
                    )
                    try:
                        fetcher.esperar(espera)
                    except CicloCancelado:
                        cancelo = True
                        avisar_cancelado()
                        break
                    i = consultados = fallas = cambios_api = no_hallados = seguidas = 0  # lo exitoso se salta
                    continue
                sin_respuesta = True  # lo fallido queda en el reporte y se vuelve a consultar al reanudar
                pendientes = store.pendientes(ciclo_id, len(radicados))
                avisar_fn(
                    f"El portal no responde: fallaron {fallas} de {consultados} consultas, también después de "
                    f"esperar {sum(ESPERAS_CAIDA) // 60} min. Quedan {pendientes} sin consultar. {PROTOCOLO}"
                )
                break
            if r5:  # con cambio de la API: se detiene sin esperar
                detenido = True
                avisar_fn(
                    f"Fuente no disponible: fallaron {fallas} de {consultados} consultas. "
                    "Ciclo detenido, activar consulta manual."
                )
            elif i <= ultimo:
                fetcher.pausar()
        if progreso:
            progreso(i, len(radicados), r.radicado)

    # los contadores de la pasada sirven para detectar caídas; el estado final mira el último resultado de cada uno
    finales = por_radicado.values()
    consultados = len(por_radicado)
    fallas = sum(c.falla_portal for c in finales)
    cambios_api = sum(c.estado == ERROR for c in finales)
    no_hallados = sum(c.no_hallado for c in finales)
    sin_consultar = sum(c.falla_portal and c.estado == FALLIDA for c in finales)
    if sin_consultar and not (cancelo or bloqueado or sin_respuesta or detenido):
        avisar_fn(
            f"{sin_consultar} radicado(s) no se pudieron consultar por fallas del portal, ni en el repaso final. "
            "Salen como NO VERIFICADO en el reporte: consultarlos a mano o volver a lanzar la consulta más tarde."
        )
    fuente_caida = consultados > 0 and fallas / consultados > max_fallas
    muchos_no_hallados = consultados >= MIN_MUESTRA and no_hallados / consultados > max_fallas
    if muchos_no_hallados:  # que casi ningún radicado exista apunta a la API, no a la lista
        avisar_fn(
            f"ALERTA: el portal no encontró {no_hallados} de {consultados} radicados; la API posiblemente cambió. "
            "Revisar la herramienta y usar la consulta manual mientras tanto."
        )
    if cambios_api:
        avisar_fn(
            f"ALERTA: la API de la Rama Judicial posiblemente cambió. {cambios_api} de {consultados} "
            "consultas devolvieron una respuesta con una forma inesperada. "
            "Revisar la herramienta y usar la consulta manual mientras tanto."
        )
    if cancelo:
        estado = ESTADO_CANCELADO
    elif bloqueado:
        estado = ESTADO_PAUSADO
    elif sin_respuesta:
        estado = ESTADO_SIN_RESPUESTA
    elif detenido:  # solo se detiene sin esperar si cambió la API
        estado = "Detenido: posible cambio en la API"
    elif cambios_api or muchos_no_hallados:
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
    pendientes = store.pendientes(ciclo_id, len(radicados)) if bloqueado or cancelo or sin_respuesta else 0
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


def _mantenimiento(cfg, store, avisar_fn, hoy) -> None:
    """Archiva reportes y respalda la base. Un fallo se avisa y nunca tumba el ciclo."""
    m = cfg.get("mantenimiento", {})
    carpeta = Path(cfg["salida"]["carpeta_reportes"])
    try:
        movidos = archivar_reportes(carpeta, hoy, m.get("archivar_reportes_tras_dias", 14))
        if m.get("borrar_archivo_tras_dias", 0) > 0:
            borrar_archivo_antiguo(carpeta, hoy, m["borrar_archivo_tras_dias"])
        if movidos:
            avisar_fn(f"Mantenimiento: {len(movidos)} reportes archivados.")
    except Exception as e:
        avisar_fn(f"Mantenimiento: no se pudo archivar los reportes ({type(e).__name__}: {e})")
    try:
        destino = m.get("carpeta_respaldo") or Path(cfg["salida"]["base_datos"]).parent / "respaldo"
        ruta = respaldar_base(
            store.con, destino, hoy, m.get("respaldo_cada_dias", 7), m.get("respaldos_a_conservar", 8)
        )
        if ruta:
            avisar_fn(f"Mantenimiento: respaldo creado en {ruta}.")
    except Exception as e:
        avisar_fn(f"Mantenimiento: falló el respaldo de la base de datos ({type(e).__name__}: {e})")


@contextmanager
def _sin_cancelar(ruta):
    """Una petición de cancelar vieja no cancela un ciclo nuevo; la actual se borra al terminar."""
    ruta.unlink(missing_ok=True)
    try:
        yield
    finally:
        ruta.unlink(missing_ok=True)


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

    if not consultas_activas(Path(cfg["salida"]["base_datos"]).parent):  # interruptor del equipo; --forzar no lo salta
        msg = "Las consultas están apagadas en este equipo. Enciéndalas desde la ventana (botón «Encender consultas»)."
        aviso(msg)
        return Ejecucion(3, msg, None)
    ruta_cancelar = Path(cfg["salida"]["base_datos"]).parent / "cancelar.txt"
    minimo = cfg.get("ejecucion", {}).get("min_minutos_entre_ciclos", 30)
    inicio = datetime.now()
    try:
        with Bloqueo(Path(cfg["salida"]["base_datos"]).parent) as bloqueo, _sin_cancelar(ruta_cancelar):
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
            fuente = crear_fuente(cfg["fuente"])
            radicados = fuente.cargar()
            sin_radicado = getattr(fuente, "filas_sin_radicado", 0)
            if sin_radicado:
                aviso(
                    f"{sin_radicado} fila(s) del Excel tienen datos pero van sin radicado "
                    "y no se consultan: revisar el cuadro."
                )
            if solo_radicado:
                radicados = [r for r in radicados if r.radicado == solo_radicado]
            portal = cfg["portal"]
            cancelado = ruta_cancelar.exists
            fetcher = Fetcher(
                pausa=portal["pausa_segundos"],
                reintentos=portal["reintentos"],
                espera=portal["espera_segundos"],
                timeout=portal["timeout_segundos"],
                pausa_peticiones=portal.get("pausa_peticiones_segundos", 1.5),
                consultar_detalle=portal.get("consultar_detalle", False),
                reintentos_bloqueo=portal.get("reintentos_bloqueo", 3),
                espera_bloqueo=portal.get("espera_bloqueo_segundos", 60),
                cancelado=cancelado,
                avisar=lambda t: _registrar(t, log),  # solo al log: es para medir la cuota, no para la persona
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
                cancelado=cancelado,
                alertar_primera_dias=leer_dias(
                    Path(cfg["salida"]["base_datos"]).parent,
                    cfg.get("primera_consulta", {}).get("alertar_ultimos_dias", DIAS_POR_DEFECTO),
                ),
            )
            _mantenimiento(cfg, store, aviso, datetime.now().date())
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
    mensaje = f"{res.estado}. {PROTOCOLO}" if res.estado.startswith("Pausado") else ""  # la ventana dice qué hacer
    return Ejecucion(0 if res.estado == "Completo" else 1, mensaje, res)


def ejecutar(argv=None) -> int:
    """0 = ciclo completo, 1 = detenido o con fallas, 2 = error inesperado, 3 = no se ejecutó (candado o límite)."""
    p = argparse.ArgumentParser(prog="consultor")
    p.add_argument("comando", choices=["run", "ventana"])
    p.add_argument("--config", default="config.toml")
    p.add_argument("--solo-radicado", help="consulta un único radicado, para pruebas")
    p.add_argument("--forzar", action="store_true", help="salta el límite entre ejecuciones (no el candado)")
    p.add_argument("--abrir", action="store_true", help="abre el Excel al terminar")
    args = p.parse_args(argv)

    if args.comando == "ventana":
        from .ventana import abrir  # tkinter solo se exige para la ventana, no para "run"

        return abrir(args.config)
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
