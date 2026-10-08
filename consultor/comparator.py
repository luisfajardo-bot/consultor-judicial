from .models import (
    EXITOSA,
    NO_VERIFICADO,
    POSIBLE_NOVEDAD,
    SIN_CAMBIO,
    Consulta,
    Veredicto,
)


def comparar(consulta: Consulta, conocidas: set[int], tiene_referencia: bool) -> Veredicto:
    """Clasifica una consulta. No toca red ni disco."""
    if consulta.estado != EXITOSA:
        return Veredicto(NO_VERIFICADO, motivo=consulta.motivo)
    if not tiene_referencia:
        return Veredicto(SIN_CAMBIO, motivo="referencia inicial")  # R2
    nuevas = tuple(a for a in consulta.actuaciones if a.id_reg_actuacion not in conocidas)
    if nuevas:
        return Veredicto(POSIBLE_NOVEDAD, nuevas=nuevas)  # R1
    return Veredicto(SIN_CAMBIO)
