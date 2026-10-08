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
