import sys
from pathlib import Path

from .consola import redirigir_si_no_hay_consola
from .main import ejecutar

if __name__ == "__main__":
    redirigir_si_no_hay_consola(Path("reportes") / "consola.log")
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None:
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(ejecutar(sys.argv[1:]))
