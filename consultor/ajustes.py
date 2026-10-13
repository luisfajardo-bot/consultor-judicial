"""Ajustes que cambian los abogados desde la pantalla.

Se guardan en datos/ajustes.json y no en config.toml, que edita Sistemas y lleva comentarios.
Si el archivo existe manda sobre config.toml; si no, rige config.toml y luego el valor por defecto.
"""

import json
import os
from pathlib import Path

DIAS_POR_DEFECTO = 7
DIAS_MAXIMO = 365
ARCHIVO = "ajustes.json"
CLAVE = "alertar_ultimos_dias"


def _valido(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and 0 <= valor <= DIAS_MAXIMO


def leer_dias(carpeta_datos, defecto=DIAS_POR_DEFECTO) -> int:
    try:
        valor = json.loads((Path(carpeta_datos) / ARCHIVO).read_text(encoding="utf-8"))[CLAVE]
    except (OSError, ValueError, KeyError, TypeError):
        return defecto
    return valor if _valido(valor) else defecto


def guardar_dias(carpeta_datos, valor) -> int:
    """Guarda los días y los devuelve. Lanza ValueError con un mensaje para mostrar tal cual."""
    try:
        dias = int(valor.strip() if isinstance(valor, str) else valor)
    except (ValueError, TypeError):
        dias = -1
    if isinstance(valor, bool) or not _valido(dias):
        raise ValueError(f"Escribe un número entero de días entre 0 y {DIAS_MAXIMO}.")
    carpeta = Path(carpeta_datos)
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = carpeta / (ARCHIVO + ".tmp")
    tmp.write_text(json.dumps({CLAVE: dias}), encoding="utf-8")
    os.replace(tmp, carpeta / ARCHIVO)
    return dias
