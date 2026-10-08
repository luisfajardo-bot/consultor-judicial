from consultor.consola import barra


def test_barra_vacia_a_medias_y_llena():
    assert barra(0, 10, ancho=10) == "[----------] 0/10"
    assert barra(5, 10, ancho=10) == "[#####-----] 5/10"
    assert barra(10, 10, ancho=10) == "[##########] 10/10"


def test_barra_con_total_cero_no_divide_por_cero():
    assert barra(0, 0, ancho=4) == "[####] 0/0"
