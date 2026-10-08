from datetime import datetime, timedelta

from consultor.models import EXITOSA, Actuacion, Consulta


def act(i, fecha="2026-05-15", texto="Al despacho", radicado="11001400307720210114700", anotacion=""):
    return Actuacion(
        id_reg_actuacion=i,
        radicado=radicado,
        fecha_actuacion=fecha,
        actuacion=texto,
        anotacion=anotacion,
    )


def ok(*actuaciones, despacho="JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ"):
    return Consulta(
        EXITOSA,
        id_proceso=1,
        despacho=despacho,
        ultima_actualizacion="2026-10-08T08:29:32",
        actuaciones=tuple(actuaciones),
    )


class Reloj:
    def __init__(self, inicio=datetime(2026, 10, 12, 7, 0, 0)):
        self.actual = inicio

    def __call__(self):
        return self.actual

    def avanzar(self, dias=2):
        self.actual += timedelta(days=dias)
