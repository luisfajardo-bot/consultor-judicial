import pytest

tk = pytest.importorskip("tkinter")

import consultor.main as main_mod  # noqa: E402
from consultor.bloqueo import Bloqueo  # noqa: E402
from consultor.ventana import Ventana  # noqa: E402
from tests.test_main import preparar  # noqa: E402


@pytest.fixture(scope="session")
def _tk_unico():
    # Crear y destruir varios Tk() en un mismo proceso falla de forma intermitente en Windows.
    # Se crea uno para toda la sesión de pruebas, como hace la aplicación real.
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"sin entorno gráfico: {e}")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def raiz(_tk_unico):
    ventana = tk.Toplevel(_tk_unico)
    ventana.withdraw()
    yield ventana
    ventana.destroy()


def _cfg(tmp_path, monkeypatch):
    args = preparar(tmp_path, monkeypatch)
    return main_mod.cargar_config(args[args.index("--config") + 1])


def test_sin_consultas_previas_muestra_el_texto_inicial_y_habilita_el_boton(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch))
    v.refrescar()
    assert "Todavía no se ha hecho ninguna consulta" in v.etiqueta_resumen.cget("text")
    assert str(v.boton_consultar.cget("state")) == "normal"


def test_con_otro_ciclo_corriendo_muestra_el_avance_y_deshabilita_el_boton(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg)
        v.refrescar()
        assert "12 de 44" in v.etiqueta_avance.cget("text")
        assert float(v.barra["value"]) == 12 and float(v.barra["maximum"]) == 44
        assert str(v.boton_consultar.cget("state")) == "disabled"


def test_consultar_ahora_corre_en_un_hilo_y_muestra_el_resultado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "terminada" in v.etiqueta_estado.cget("text").lower()
    assert "1 consultados" in v.etiqueta_resumen.cget("text")


def test_si_el_ciclo_es_rechazado_se_muestra_el_mensaje(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    main_mod.ejecutar_ciclo(cfg)  # deja un ciclo reciente: el siguiente será rechazado por el límite
    v = Ventana(raiz, cfg)
    v.boton_consultar.invoke()
    v.hilo.join(timeout=30)
    v.sondear()
    assert "espera hasta las" in v.etiqueta_estado.cget("text")
