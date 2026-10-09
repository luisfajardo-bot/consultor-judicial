import sys
from pathlib import Path


def barra(hecho: int, total: int, ancho: int = 30) -> str:
    lleno = ancho if total == 0 else int(ancho * hecho / total)
    return f"[{'#' * lleno}{'-' * (ancho - lleno)}] {hecho}/{total}"


def redirigir_si_no_hay_consola(ruta) -> None:
    """Con pythonw.exe no hay consola (stdout/stderr son None): la salida y los errores van a un archivo."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    archivo = open(ruta, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = archivo
    if sys.stderr is None:
        sys.stderr = archivo
