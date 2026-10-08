from datetime import datetime, timedelta

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


def test_alerta_pendiente_de_otro_ciclo_aparece_en_el_reporte_siguiente(store):
    c2 = _con_novedad(store)            # alerta Pendiente nacida en el ciclo 2
    store.cerrar_ciclo(c2, "Completo", AHORA)
    c3 = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c3, R.radicado, ok(act(2), act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    filas = store.filas_reporte(c3)
    pendientes = [f for f in filas if f["alerta_id"]]
    assert len(pendientes) == 1
    assert pendientes[0]["resultado"] == POSIBLE_NOVEDAD
    assert pendientes[0]["decision"] == PENDIENTE
    assert "ciclo" in pendientes[0]["motivo"]


def test_alerta_ya_decidida_no_reaparece(store):
    c2 = _con_novedad(store)
    alerta_id = store.filas_reporte(c2)[0]["alerta_id"]
    store.registrar_decision(alerta_id, DESCARTADA, "Alisson", AHORA)
    store.cerrar_ciclo(c2, "Completo", AHORA)
    c3 = store.iniciar_ciclo(AHORA)
    store.registrar_resultado(c3, R.radicado, ok(act(2), act(1)), Veredicto(SIN_CAMBIO), "", AHORA)
    assert [f for f in store.filas_reporte(c3) if f["alerta_id"]] == []


def test_ciclos_abiertos_de_dias_anteriores_se_marcan_interrumpidos(store):
    viejo = store.iniciar_ciclo(AHORA)
    manana = AHORA + timedelta(days=1)
    assert store.cerrar_interrumpidos(manana) == 1
    assert store.cerrar_interrumpidos(manana) == 0
    assert store.iniciar_ciclo(manana) != viejo
