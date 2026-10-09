import subprocess
import sys
import time

import pytest

from consultor.bloqueo import Bloqueo, CicloEnCurso, ciclo_en_curso


def test_el_segundo_bloqueo_falla_y_muestra_el_estado(tmp_path):
    with Bloqueo(tmp_path) as b:
        b.publicar("06:30 | 12 de 44")
        with pytest.raises(CicloEnCurso) as e:
            with Bloqueo(tmp_path):
                pass
        assert "12 de 44" in e.value.estado


def test_se_libera_al_salir(tmp_path):
    with Bloqueo(tmp_path):
        pass
    with Bloqueo(tmp_path):  # no lanza
        pass
    assert not (tmp_path / "estado.txt").exists()


def test_se_libera_si_el_proceso_muere(tmp_path):
    codigo = (
        "import sys, time\n"
        "from consultor.bloqueo import Bloqueo\n"
        f"b = Bloqueo(r'{tmp_path}').__enter__()\n"
        "print('listo', flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "listo"
        with pytest.raises(CicloEnCurso):
            with Bloqueo(tmp_path):
                pass
    finally:
        proc.kill()
        proc.wait()
    # el sistema operativo libera el candado al morir el proceso; en Windows puede tardar unos ms
    for _ in range(50):
        try:
            with Bloqueo(tmp_path):
                break
        except CicloEnCurso:
            time.sleep(0.1)
    else:
        pytest.fail("el candado no se liberó tras morir el proceso")


def test_ciclo_en_curso_es_falso_si_nadie_tiene_el_candado(tmp_path):
    assert ciclo_en_curso(tmp_path) is False


def test_ciclo_en_curso_es_verdadero_mientras_alguien_lo_tiene(tmp_path):
    with Bloqueo(tmp_path):
        assert ciclo_en_curso(tmp_path) is True
    assert ciclo_en_curso(tmp_path) is False


def test_sondear_borra_un_estado_viejo_pero_no_toca_uno_vivo(tmp_path):
    (tmp_path / "estado.txt").write_text("09:00 | 1 de 41", encoding="utf-8")
    assert ciclo_en_curso(tmp_path) is False
    assert not (tmp_path / "estado.txt").exists()
    with Bloqueo(tmp_path) as b:
        b.publicar("09:00 | 5 de 41")
        assert ciclo_en_curso(tmp_path) is True
        assert (tmp_path / "estado.txt").read_text(encoding="utf-8") == "09:00 | 5 de 41"


def test_un_choque_breve_con_el_sondeo_no_rechaza_al_ciclo(tmp_path, monkeypatch):
    # Un sondeo de la ventana puede tener el candado unos milisegundos justo cuando arranca un ciclo.
    import consultor.bloqueo as m

    intentos = []
    original = m._bloquear

    def inestable(fd):
        intentos.append(1)
        if len(intentos) < 3:
            raise OSError("ocupado un instante")
        return original(fd)

    monkeypatch.setattr(m, "_bloquear", inestable)
    with Bloqueo(tmp_path):
        pass
    assert len(intentos) == 3
