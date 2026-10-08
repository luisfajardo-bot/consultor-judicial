import sys

from .main import ejecutar

if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None:
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(ejecutar(sys.argv[1:]))
