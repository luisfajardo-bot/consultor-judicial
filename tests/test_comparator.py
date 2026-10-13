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


def test_nuevas_con_fecha_anterior_a_la_ultima_conocida_se_reportan_todas():
    # El despacho puede registrar hoy actuaciones con fechas viejas: se reportan todas
    # las que no se habían visto, sin importar su fecha.
    v = comparar(
        ok(
            act(13, fecha="2026-10-06"),
            act(12, fecha="2026-10-07"),
            act(11, fecha="2026-09-30"),
            act(10, fecha="2026-10-07"),
        ),
        {10, 12},
        True,
    )
    assert v.resultado == POSIBLE_NOVEDAD
    assert {a.id_reg_actuacion for a in v.nuevas} == {11, 13}


def test_primera_consulta_alerta_las_registradas_desde_la_fecha_de_corte():
    # El 08/10 se registró una actuación con fecha del 06/10: cuenta por la fecha de registro.
    v = comparar(
        ok(
            act(3, fecha="2026-10-06", registro="2026-10-08"),
            act(2, fecha="2026-10-07", registro="2026-10-07"),
            act(1, fecha="2026-05-15", registro="2026-05-15"),
        ),
        set(),
        False,
        desde="2026-10-07",
    )
    assert v.resultado == POSIBLE_NOVEDAD
    assert [a.id_reg_actuacion for a in v.nuevas] == [3, 2]
    assert "referencia inicial" in v.motivo


def test_primera_consulta_sin_recientes_sigue_siendo_referencia():
    v = comparar(ok(act(1, registro="2026-05-15")), set(), False, desde="2026-10-07")
    assert v.resultado == SIN_CAMBIO
    assert v.motivo == "referencia inicial"


def test_primera_consulta_sin_fecha_de_registro_usa_la_fecha_de_actuacion():
    v = comparar(ok(act(1, fecha="2026-10-08", registro="")), set(), False, desde="2026-10-07")
    assert v.resultado == POSIBLE_NOVEDAD


def test_primera_consulta_sin_fecha_de_corte_no_alerta():
    v = comparar(ok(act(1, fecha="2026-10-08", registro="2026-10-08")), set(), False)
    assert v.resultado == SIN_CAMBIO
