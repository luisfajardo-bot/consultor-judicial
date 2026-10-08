import shutil
import sqlite3
from datetime import date, timedelta

import pytest

import consultor.mantenimiento as mant
from consultor.mantenimiento import archivar_reportes, borrar_archivo_antiguo, respaldar_base

HOY = date(2026, 10, 8)


def crear(carpeta, nombre):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    ruta.write_bytes(b"x")
    return ruta


def nombre(n, dias_atras):
    return f"reporte_ciclo_{n:04d}_{HOY - timedelta(days=dias_atras):%Y-%m-%d}.xlsx"


def test_archiva_lo_viejo_y_deja_lo_reciente(tmp_path):
    for n, d in [(1, 30), (2, 20), (3, 3)]:
        crear(tmp_path, nombre(n, d))
    movidos = archivar_reportes(tmp_path, HOY, 14)
    assert len(movidos) == 2
    for n, d in [(1, 30), (2, 20)]:
        f = HOY - timedelta(days=d)
        assert (tmp_path / "archivo" / f"{f:%Y-%m}" / nombre(n, d)).exists()
        assert not (tmp_path / nombre(n, d)).exists()
    assert (tmp_path / nombre(3, 3)).exists()


def test_el_de_mayor_numero_no_se_archiva_aunque_sea_viejo(tmp_path):
    crear(tmp_path, nombre(7, 60))
    assert archivar_reportes(tmp_path, HOY, 14) == []
    assert (tmp_path / nombre(7, 60)).exists()


def test_nombres_que_no_cuadran_y_temporales_no_se_tocan(tmp_path):
    crear(tmp_path, nombre(9, 1))
    otros = ["notas.xlsx", "reporte_algo.xlsx", "~$" + nombre(1, 90)]
    for o in otros:
        crear(tmp_path, o)
    assert archivar_reportes(tmp_path, HOY, 14) == []
    assert all((tmp_path / o).exists() for o in otros)


def test_es_idempotente_y_no_sobrescribe(tmp_path):
    crear(tmp_path, nombre(1, 30))
    crear(tmp_path, nombre(2, 1))
    assert len(archivar_reportes(tmp_path, HOY, 14)) == 1
    assert archivar_reportes(tmp_path, HOY, 14) == []
    # el destino ya existe: el origen se queda y el destino no cambia
    f = HOY - timedelta(days=30)
    destino = tmp_path / "archivo" / f"{f:%Y-%m}" / nombre(1, 30)
    destino.write_bytes(b"original")
    origen = crear(tmp_path, nombre(1, 30))
    assert archivar_reportes(tmp_path, HOY, 14) == []
    assert origen.exists() and destino.read_bytes() == b"original"


def test_un_archivo_que_no_se_puede_mover_se_omite(tmp_path, monkeypatch):
    for n, d in [(1, 40), (2, 35), (3, 30), (4, 1)]:
        crear(tmp_path, nombre(n, d))
    real = shutil.move

    def move(src, dst):
        if nombre(2, 35) in str(src):
            raise PermissionError("abierto en Excel")
        return real(src, dst)

    monkeypatch.setattr(mant.shutil, "move", move)
    movidos = archivar_reportes(tmp_path, HOY, 14)
    assert len(movidos) == 2
    assert (tmp_path / nombre(2, 35)).exists()
    assert not (tmp_path / nombre(1, 40)).exists() and not (tmp_path / nombre(3, 30)).exists()


def test_dias_cero_no_mueve_nada(tmp_path):
    crear(tmp_path, nombre(1, 90))
    crear(tmp_path, nombre(2, 80))
    assert archivar_reportes(tmp_path, HOY, 0) == []
    assert (tmp_path / nombre(1, 90)).exists()


def test_borrar_archivo_antiguo(tmp_path):
    viejo = HOY - timedelta(days=200)
    medio = HOY - timedelta(days=30)
    a = crear(tmp_path / "archivo" / f"{viejo:%Y-%m}", nombre(1, 200))
    b = crear(tmp_path / "archivo" / f"{medio:%Y-%m}", nombre(2, 30))
    assert borrar_archivo_antiguo(tmp_path, HOY, 0) == []
    assert a.exists() and b.exists()
    assert borrar_archivo_antiguo(tmp_path, HOY, 90) == [a]
    assert not a.exists() and b.exists()
    assert not a.parent.exists()  # carpeta vacía eliminada
    assert b.parent.exists()


def base(tmp_path, filas=3):
    con = sqlite3.connect(str(tmp_path / "origen.db"))
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    with con:
        con.executemany("INSERT INTO t (v) VALUES (?)", [(f"fila{i}",) for i in range(filas)])
    return con


def filas(ruta):
    con = sqlite3.connect(str(ruta))
    try:
        return con.execute("SELECT id, v FROM t ORDER BY id").fetchall()
    finally:
        con.close()


def test_respaldo_crea_copia_con_las_mismas_filas(tmp_path):
    con = base(tmp_path)
    ruta = respaldar_base(con, tmp_path / "respaldo", HOY)
    assert ruta == tmp_path / "respaldo" / "consultor_2026-10-08.db"
    assert filas(ruta) == filas(tmp_path / "origen.db") and len(filas(ruta)) == 3


def test_respaldo_respeta_la_frecuencia(tmp_path):
    con = base(tmp_path)
    carpeta = tmp_path / "respaldo"
    assert respaldar_base(con, carpeta, HOY) is not None
    assert respaldar_base(con, carpeta, HOY + timedelta(days=3)) is None
    assert len(list(carpeta.glob("*.db"))) == 1
    assert respaldar_base(con, carpeta, HOY + timedelta(days=8)) is not None
    assert len(list(carpeta.glob("*.db"))) == 2
    assert respaldar_base(con, carpeta, HOY + timedelta(days=30), cada_dias=0) is None


def test_respaldo_conserva_solo_los_mas_recientes(tmp_path):
    con = base(tmp_path)
    carpeta = tmp_path / "respaldo"
    for i in range(5):
        assert respaldar_base(con, carpeta, HOY + timedelta(days=8 * i), conservar=3) is not None
    quedan = sorted(p.name for p in carpeta.glob("*.db"))
    esperado = [f"consultor_{HOY + timedelta(days=8 * i):%Y-%m-%d}.db" for i in (2, 3, 4)]
    assert quedan == esperado


def test_respaldo_con_la_base_abierta_incluye_lo_confirmado(tmp_path):
    con = base(tmp_path)  # la conexión sigue abierta durante el respaldo
    with con:
        con.execute("INSERT INTO t (v) VALUES ('reciente')")
    ruta = respaldar_base(con, tmp_path / "respaldo", HOY)
    assert ("reciente" in [v for _, v in filas(ruta)])
    assert len(filas(ruta)) == 4
    with con:  # la base de origen sigue utilizable
        con.execute("INSERT INTO t (v) VALUES ('despues')")
    assert len(filas(tmp_path / "origen.db")) == 5


def test_respaldo_que_no_pasa_la_integridad_se_borra_y_falla(tmp_path, monkeypatch):
    con = base(tmp_path)
    carpeta = tmp_path / "respaldo"
    llamadas = []

    def mala(ruta):
        llamadas.append(ruta)
        assert ruta.exists()  # se verificó un respaldo real, antes de borrarlo
        return "*** in database main ***"

    monkeypatch.setattr(mant, "_integridad", mala)
    with pytest.raises(RuntimeError, match="no pasó la verificación de integridad"):
        respaldar_base(con, carpeta, HOY)
    assert llamadas
    assert list(carpeta.glob("*.db")) == [] and list(carpeta.glob("*.tmp")) == []


def test_respaldo_normal_no_deja_tmp(tmp_path):
    con = base(tmp_path)
    carpeta = tmp_path / "respaldo"
    respaldar_base(con, carpeta, HOY)
    assert list(carpeta.glob("*.tmp")) == []
