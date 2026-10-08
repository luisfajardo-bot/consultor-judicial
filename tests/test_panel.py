import os
import time
from datetime import datetime, timedelta

from consultor.models import SIN_CAMBIO, Radicado, Veredicto
from consultor.panel import (
    Avance,
    leer_avance,
    resumen_ultimo_ciclo,
    texto_avance,
    texto_resumen,
    ultimo_reporte,
)
from consultor.store import Store
from tests.utiles import act, ok

AHORA = datetime(2026, 10, 12, 9, 0, 0)


def leer_avance_falso(hecho, total, segundos):
    return Avance(hecho, total, segundos, "09:00")


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
