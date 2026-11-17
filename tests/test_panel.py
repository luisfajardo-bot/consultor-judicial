import os
import time
from datetime import date, datetime, timedelta

from consultor.bloqueo import Bloqueo
from consultor.models import SIN_CAMBIO, Radicado, Veredicto
from consultor.panel import (
    Avance,
    ConfigAlertas,
    accion_al_cerrar,
    config_alertas,
    contar_para_regla,
    evaluar_obligacion,
    separar,
    texto_dias_guardado,
    texto_pestana_rango,
    leer_avance,
    resumen_ultimo_ciclo,
    solicitar_cancelacion,
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
    with Bloqueo(tmp_path) as b:
        b.publicar("09:00 | 12 de 44")
        ahora = (tmp_path / "estado.txt").stat().st_mtime + 150
        a = leer_avance(tmp_path, ahora=ahora)
    assert (a.hecho, a.total, a.hora_inicio) == (12, 44, "09:00")
    assert round(a.segundos_sin_avance) == 150


def test_leer_avance_con_texto_ilegible_es_none(tmp_path):
    with Bloqueo(tmp_path) as b:
        b.publicar("basura")
        assert leer_avance(tmp_path) is None


def test_un_estado_sin_candado_es_un_resto_viejo_y_se_ignora(tmp_path):
    (tmp_path / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    assert leer_avance(tmp_path) is None
    assert not (tmp_path / "estado.txt").exists()


def test_solicitar_cancelacion_solo_actua_si_hay_un_ciclo_corriendo(tmp_path):
    assert solicitar_cancelacion(tmp_path) is False
    assert not (tmp_path / "cancelar.txt").exists()
    with Bloqueo(tmp_path):
        assert solicitar_cancelacion(tmp_path) is True
        assert (tmp_path / "cancelar.txt").exists()


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


HOY = date(2026, 11, 17)


def _p(*dias_atras):
    return [{"id": i, "detectada": f"{HOY - timedelta(days=d)}T08:00:00"} for i, d in enumerate(dias_atras)]


def test_separar_frontera_inclusiva():
    en, ant = separar(_p(0, 7, 8), HOY, 7)
    assert [x["id"] for x in en] == [0, 1] and [x["id"] for x in ant] == [2]


def test_separar_con_cero_dias_deja_solo_hoy():
    en, ant = separar(_p(0, 1), HOY, 0)
    assert [x["id"] for x in en] == [0] and [x["id"] for x in ant] == [1]


def test_evaluar_obligacion_se_activa_sobre_30_y_se_libera_bajo_10():
    c = ConfigAlertas(exigir=True)
    assert evaluar_obligacion(False, 30, c) is False
    assert evaluar_obligacion(False, 31, c) is True
    assert evaluar_obligacion(True, 10, c) is True
    assert evaluar_obligacion(True, 9, c) is False
    assert evaluar_obligacion(True, 50, ConfigAlertas(exigir=False)) is False


def test_la_regla_usa_su_propio_corte_y_no_el_campo_dias():
    p = _p(*([20] * 31))
    assert contar_para_regla(p, HOY, ConfigAlertas(exigir=True, dias_corte=7)) == 31


def test_accion_al_cerrar():
    c = ConfigAlertas(exigir=True)
    assert accion_al_cerrar(True, 44, 3, 7, c).tipo == "bloquear"
    assert "Faltan 35." in accion_al_cerrar(True, 44, 3, 7, c).texto
    a = accion_al_cerrar(False, 0, 3, 7, c)
    assert a.tipo == "preguntar" and a.texto == "Quedan 3 alertas por decidir de los últimos 7 días. ¿Cerrar de todas formas?"
    assert accion_al_cerrar(False, 0, 0, 7, c).tipo == "cerrar"


def test_config_alertas_por_defecto_apagada():
    assert config_alertas({}) == ConfigAlertas(False, 30, 10, 7)


def test_textos_de_pestanas_y_guardado():
    assert texto_pestana_rango(7, 5) == "Por decidir · últimos 7 días (5)"
    assert texto_pestana_rango(0, 2) == "Por decidir · hoy (2)"
    assert texto_dias_guardado(0).startswith("Guardado: 0 días. No se avisará nada")
