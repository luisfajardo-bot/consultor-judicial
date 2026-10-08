import re
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

PATRON = re.compile(r"reporte_ciclo_(\d{4})_(\d{4})-(\d{2})-(\d{2})\.xlsx")


def _leer(ruta: Path):
    """(numero, fecha) según el nombre, o None si no cuadra con el patrón."""
    m = PATRON.fullmatch(ruta.name)
    if not m:
        return None
    try:
        return int(m[1]), date(int(m[2]), int(m[3]), int(m[4]))
    except ValueError:
        return None


def archivar_reportes(carpeta, hoy: date, dias: int = 14) -> list[Path]:
    """Mueve a carpeta/archivo/AAAA-MM/ los reportes viejos, menos el de mayor número."""
    if dias <= 0:
        return []
    carpeta = Path(carpeta)
    reportes = [(d, p) for p in carpeta.glob("reporte_ciclo_*.xlsx") if (d := _leer(p))]
    if not reportes:
        return []
    mayor = max(d[0] for d, _ in reportes)
    limite = hoy - timedelta(days=dias)
    movidos = []
    for (numero, fecha), ruta in sorted(reportes, key=lambda x: x[1].name):
        if numero == mayor or fecha >= limite:
            continue
        destino = carpeta / "archivo" / f"{fecha:%Y-%m}" / ruta.name
        if destino.exists():
            continue
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ruta), str(destino))
        except OSError:
            continue  # abierto en Excel: se reintenta en el siguiente ciclo
        movidos.append(destino)
    return movidos


def borrar_archivo_antiguo(carpeta, hoy: date, dias: int) -> list[Path]:
    """Borra de carpeta/archivo/ los reportes con fecha anterior a hoy - dias y las carpetas vacías."""
    if dias <= 0:
        return []
    base = Path(carpeta) / "archivo"
    limite = hoy - timedelta(days=dias)
    borrados = []
    for ruta in sorted(base.rglob("reporte_ciclo_*.xlsx")):
        d = _leer(ruta)
        if not d or d[1] >= limite:
            continue
        try:
            ruta.unlink()
        except OSError:
            continue
        borrados.append(ruta)
    for sub in sorted(base.glob("*"), reverse=True):
        if sub.is_dir():
            try:
                sub.rmdir()  # solo funciona si está vacía
            except OSError:
                pass
    return borrados


PATRON_RESPALDO = re.compile(r"consultor_(\d{4})-(\d{2})-(\d{2})\.db")


def _integridad(ruta: Path) -> str:
    con = sqlite3.connect(str(ruta))
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def _fecha_respaldo(ruta: Path):
    m = PATRON_RESPALDO.fullmatch(ruta.name)
    try:
        return date(int(m[1]), int(m[2]), int(m[3])) if m else None
    except ValueError:
        return None


def respaldar_base(con, carpeta_respaldo, hoy: date, cada_dias: int = 7, conservar: int = 8) -> Path | None:
    """Respalda la base abierta con la API de SQLite. None si aún no toca o está desactivado."""
    if cada_dias <= 0:
        return None
    carpeta = Path(carpeta_respaldo)
    carpeta.mkdir(parents=True, exist_ok=True)
    fechas = [f for p in carpeta.glob("consultor_*.db") if (f := _fecha_respaldo(p))]
    if fechas and (hoy - max(fechas)).days < cada_dias:
        return None
    destino = carpeta / f"consultor_{hoy:%Y-%m-%d}.db"
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.unlink(missing_ok=True)
    copia = sqlite3.connect(str(tmp))
    try:
        con.backup(copia)
    except BaseException:
        copia.close()
        tmp.unlink(missing_ok=True)
        raise
    copia.close()
    if _integridad(tmp) != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError("el respaldo no pasó la verificación de integridad")
    tmp.replace(destino)
    if conservar > 0:
        todos = sorted((f, p) for p in carpeta.glob("consultor_*.db") if (f := _fecha_respaldo(p)))
        for _, p in todos[:-conservar]:
            p.unlink(missing_ok=True)
    return destino
