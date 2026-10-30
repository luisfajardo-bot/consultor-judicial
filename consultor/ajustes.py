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
CLAVE_ACTIVAS = "consultas_activas"


def _valido(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and 0 <= valor <= DIAS_MAXIMO


def _leer(carpeta_datos) -> dict:
    try:
        datos = json.loads((Path(carpeta_datos) / ARCHIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir(carpeta_datos, datos: dict) -> None:
    carpeta = Path(carpeta_datos)
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = carpeta / (ARCHIVO + ".tmp")
    tmp.write_text(json.dumps(datos), encoding="utf-8")
    os.replace(tmp, carpeta / ARCHIVO)


def leer_dias(carpeta_datos, defecto=DIAS_POR_DEFECTO) -> int:
    valor = _leer(carpeta_datos).get(CLAVE)
    return valor if _valido(valor) else defecto


def consultas_activas(carpeta_datos) -> bool:
    """Interruptor de este equipo. Si el archivo falta o está dañado, las consultas siguen encendidas."""
    valor = _leer(carpeta_datos).get(CLAVE_ACTIVAS)
    return valor if isinstance(valor, bool) else True


def guardar_activas(carpeta_datos, activas: bool) -> bool:
    _escribir(carpeta_datos, {**_leer(carpeta_datos), CLAVE_ACTIVAS: activas})
    return activas


def guardar_dias(carpeta_datos, valor) -> int:
    """Guarda los días y los devuelve. Lanza ValueError con un mensaje para mostrar tal cual."""
    try:
        dias = int(valor.strip() if isinstance(valor, str) else valor)
    except (ValueError, TypeError):
        dias = -1
    if isinstance(valor, bool) or not _valido(dias):
        raise ValueError(f"Escribe un número entero de días entre 0 y {DIAS_MAXIMO}.")
    _escribir(carpeta_datos, {**_leer(carpeta_datos), CLAVE: dias})
    return dias
