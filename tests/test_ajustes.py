import pytest

from consultor.ajustes import DIAS_POR_DEFECTO, consultas_activas, guardar_activas, guardar_dias, leer_dias


def test_sin_archivo_se_usa_el_valor_por_defecto(tmp_path):
    assert leer_dias(tmp_path) == DIAS_POR_DEFECTO
    assert leer_dias(tmp_path, defecto=3) == 3


def test_lo_guardado_se_lee_aunque_la_carpeta_no_exista(tmp_path):
    carpeta = tmp_path / "datos"
    assert guardar_dias(carpeta, 10) == 10
    assert leer_dias(carpeta) == 10


@pytest.mark.parametrize("texto, dias", [("5", 5), (" 0 ", 0), (14, 14), ("365", 365)])
def test_acepta_numeros_enteros_en_el_rango(tmp_path, texto, dias):
    assert guardar_dias(tmp_path, texto) == dias
    assert leer_dias(tmp_path) == dias


@pytest.mark.parametrize("malo", ["", "abc", "3.5", "-1", "366", None, True])
def test_rechaza_valores_invalidos_sin_tocar_lo_guardado(tmp_path, malo):
    guardar_dias(tmp_path, 4)
    with pytest.raises(ValueError, match="entre 0 y 365"):
        guardar_dias(tmp_path, malo)
    assert leer_dias(tmp_path) == 4


def test_un_archivo_dañado_no_rompe_la_lectura(tmp_path):
    (tmp_path / "ajustes.json").write_text("{no es json", encoding="utf-8")
    assert leer_dias(tmp_path) == DIAS_POR_DEFECTO
    (tmp_path / "ajustes.json").write_text('{"alertar_ultimos_dias": 9999}', encoding="utf-8")
    assert leer_dias(tmp_path) == DIAS_POR_DEFECTO


def test_las_consultas_estan_encendidas_por_defecto_y_el_interruptor_se_guarda(tmp_path):
    assert consultas_activas(tmp_path)
    assert guardar_activas(tmp_path, False) is False
    assert not consultas_activas(tmp_path)
    guardar_activas(tmp_path, True)
    assert consultas_activas(tmp_path)


def test_interruptor_y_dias_no_se_pisan_entre_si(tmp_path):
    guardar_dias(tmp_path, 4)
    guardar_activas(tmp_path, False)
    guardar_dias(tmp_path, 9)
    assert leer_dias(tmp_path) == 9 and not consultas_activas(tmp_path)


def test_un_interruptor_dañado_deja_las_consultas_encendidas(tmp_path):
    (tmp_path / "ajustes.json").write_text("{no es json", encoding="utf-8")
    assert consultas_activas(tmp_path)
    (tmp_path / "ajustes.json").write_text('{"consultas_activas": "no"}', encoding="utf-8")
    assert consultas_activas(tmp_path)
