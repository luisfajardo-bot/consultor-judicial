import subprocess
import sys

import pytest

from consultor.bloqueo import Bloqueo, CicloEnCurso


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
    with Bloqueo(tmp_path):  # el sistema operativo liberó el candado
        pass
