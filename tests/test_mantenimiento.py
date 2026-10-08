import shutil
from datetime import date, timedelta

import pytest

import consultor.mantenimiento as mant
from consultor.mantenimiento import archivar_reportes, borrar_archivo_antiguo

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
