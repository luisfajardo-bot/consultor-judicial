from .models import (
    EXITOSA,
    NO_VERIFICADO,
    POSIBLE_NOVEDAD,
    SIN_CAMBIO,
    Consulta,
    Veredicto,
)


def comparar(
    consulta: Consulta, conocidas: set[int], tiene_referencia: bool, desde: str = ""
) -> Veredicto:
    """Clasifica una consulta. No toca red ni disco.

    `desde` (AAAA-MM-DD) solo aplica a la primera consulta de un radicado: lo registrado
    desde esa fecha se reporta como novedad en vez de quedar en silencio como referencia.
    La fecha que cuenta es la de registro: el despacho puede registrar hoy una actuación
    con fecha anterior.
    """
    if consulta.estado != EXITOSA:
        return Veredicto(NO_VERIFICADO, motivo=consulta.motivo)
    if not tiene_referencia:
        recientes = tuple(
            a for a in consulta.actuaciones if desde and (a.fecha_registro or a.fecha_actuacion) >= desde
        )
        if recientes:
            return Veredicto(POSIBLE_NOVEDAD, nuevas=recientes, motivo="referencia inicial")
        return Veredicto(SIN_CAMBIO, motivo="referencia inicial")  # R2
    nuevas = tuple(a for a in consulta.actuaciones if a.id_reg_actuacion not in conocidas)
    if nuevas:
        return Veredicto(POSIBLE_NOVEDAD, nuevas=nuevas)  # R1
    return Veredicto(SIN_CAMBIO)
