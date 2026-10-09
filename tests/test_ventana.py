import pytest

# En Linux sin librerías gráficas el import falla con ImportError, no con ModuleNotFoundError
tk = pytest.importorskip("tkinter", exc_type=ImportError)

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


def _estado(w):
    return str(w.cget("state"))


def test_sin_ciclo_el_boton_cancelar_esta_deshabilitado(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch), confirmar=lambda: True)
    v.refrescar()
    assert _estado(v.boton_cancelar) == "disabled"


def test_con_ciclo_el_boton_cancelar_esta_habilitado(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: True)
        v.refrescar()
        assert _estado(v.boton_cancelar) == "normal"


def test_si_no_se_confirma_no_se_pide_cancelar(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: False)
        v.refrescar()
        v.boton_cancelar.invoke()
        assert not (tmp_path / "datos" / "cancelar.txt").exists()


def test_al_confirmar_se_crea_cancelar_txt_y_se_avisa(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    with Bloqueo(tmp_path / "datos") as b:
        b.publicar("09:00 | 12 de 44")
        v = Ventana(raiz, cfg, confirmar=lambda: True)
        v.refrescar()
        v.boton_cancelar.invoke()
        assert (tmp_path / "datos" / "cancelar.txt").exists()
        assert "Cancelando" in v.etiqueta_estado.cget("text")
        assert _estado(v.boton_cancelar) == "disabled"


def test_si_el_ciclo_ya_termino_se_dice_que_no_hay_consulta(raiz, tmp_path, monkeypatch):
    v = Ventana(raiz, _cfg(tmp_path, monkeypatch), confirmar=lambda: True)
    v.cancelar()
    assert "No hay ninguna consulta en curso" in v.etiqueta_estado.cget("text")
    assert not (tmp_path / "datos" / "cancelar.txt").exists()


def test_un_estado_viejo_sin_candado_no_habilita_cancelar_ni_bloquea_consultar(raiz, tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    (tmp_path / "datos").mkdir(exist_ok=True)
    (tmp_path / "datos" / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    v = Ventana(raiz, cfg, confirmar=lambda: True)
    v.refrescar()
    assert _estado(v.boton_cancelar) == "disabled"
    assert _estado(v.boton_consultar) == "normal"
