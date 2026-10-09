import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    import msvcrt

    def _bloquear(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _liberar(fd):
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _bloquear(fd):
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _liberar(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)


class CicloEnCurso(Exception):
    """Ya hay otro ciclo corriendo. estado trae su avance, si lo publicó."""

    def __init__(self, estado=""):
        super().__init__(estado)
        self.estado = estado


class Bloqueo:
    def __init__(self, carpeta, reintentos=4):
        carpeta = Path(carpeta)
        self.ruta = carpeta / "consultor.lock"
        self.ruta_estado = carpeta / "estado.txt"
        self.reintentos = reintentos
        self.fd = None

    def __enter__(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.ruta, os.O_RDWR | os.O_CREAT)
        for intento in range(self.reintentos):
            try:
                _bloquear(self.fd)
                break
            except OSError:
                if intento < self.reintentos - 1:
                    time.sleep(0.1)
        else:
            os.close(self.fd)
            self.fd = None
            raise CicloEnCurso(self.leer_estado()) from None
        return self

    def __exit__(self, *exc):
        try:
            self.ruta_estado.unlink(missing_ok=True)
        finally:
            _liberar(self.fd)
            os.close(self.fd)
            self.fd = None

    def publicar(self, texto: str) -> None:
        """Deja el avance en un archivo que otro intento de ejecución puede leer."""
        tmp = self.ruta_estado.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, self.ruta_estado)

    def leer_estado(self) -> str:
        try:
            return self.ruta_estado.read_text(encoding="utf-8")
        except OSError:
            return ""


def ciclo_en_curso(carpeta) -> bool:
    """Verdadero si otro proceso tiene el candado. Si está libre, borra un estado.txt viejo."""
    try:
        with Bloqueo(carpeta, reintentos=1):
            return False
    except CicloEnCurso:
        return True
