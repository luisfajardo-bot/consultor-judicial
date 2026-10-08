from dataclasses import dataclass

EXITOSA = "Exitosa"
FALLIDA = "Fallida"
ERROR = "Error"

POSIBLE_NOVEDAD = "POSIBLE NOVEDAD"
SIN_CAMBIO = "SIN CAMBIO"
NO_VERIFICADO = "NO VERIFICADO"

PENDIENTE = "Pendiente"
CONFIRMADA = "Confirmada"
DESCARTADA = "Descartada"


@dataclass(frozen=True)
class Radicado:
    radicado: str
    empresa: str = ""
    despacho: str = ""
    calidad: str = ""


@dataclass(frozen=True)
class Actuacion:
    id_reg_actuacion: int
    radicado: str
    fecha_actuacion: str
    actuacion: str
    anotacion: str = ""
    fecha_registro: str = ""
    fecha_inicial: str = ""
    fecha_final: str = ""


@dataclass(frozen=True)
class Consulta:
    """Lo que devolvió el portal para un radicado. falla_portal cuenta para R5 (el portal falló o no devolvió el proceso)."""

    estado: str
    motivo: str = ""
    falla_portal: bool = False
    id_proceso: int | None = None
    despacho: str = ""
    ultima_actualizacion: str = ""
    actuaciones: tuple[Actuacion, ...] = ()


@dataclass(frozen=True)
class Veredicto:
    resultado: str
    nuevas: tuple[Actuacion, ...] = ()
    motivo: str = ""
