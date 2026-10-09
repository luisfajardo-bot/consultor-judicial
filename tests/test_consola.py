import sys

from consultor.consola import barra, redirigir_si_no_hay_consola


def test_barra_vacia_a_medias_y_llena():
    assert barra(0, 10, ancho=10) == "[----------] 0/10"
    assert barra(5, 10, ancho=10) == "[#####-----] 5/10"
    assert barra(10, 10, ancho=10) == "[##########] 10/10"


def test_barra_con_total_cero_no_divide_por_cero():
    assert barra(0, 0, ancho=4) == "[####] 0/0"


def test_sin_consola_la_salida_va_a_un_archivo(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ruta = tmp_path / "carpeta" / "consola.log"
    redirigir_si_no_hay_consola(ruta)
    print("hola")
    sys.stderr.write("error" + chr(10))
    sys.stdout.flush()
    sys.stderr.flush()
    texto = ruta.read_text(encoding="utf-8")
    assert "hola" in texto and "error" in texto


def test_con_consola_no_toca_nada(tmp_path, capsys):
    antes = sys.stdout
    redirigir_si_no_hay_consola(tmp_path / "x.log")
    assert sys.stdout is antes
    assert not (tmp_path / "x.log").exists()
