import requests

import pytest

from consultor.fetcher import USER_AGENT, CicloCancelado, Fetcher
from consultor.models import ERROR, EXITOSA, FALLIDA, Radicado

RAD = Radicado("11001400307720210114700")

BUSQUEDA = {
    "procesos": [
        {
            "idProceso": 108832900,
            "despacho": "JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ ",
            "fechaUltimaActuacion": "2026-05-15T00:00:00",
            "sujetosProcesales": "Demandante: PERSONA UNO | Demandado: EMPRESA",
        }
    ]
}
ACTUACIONES = {
    "actuaciones": [
        {
            "idRegActuacion": 2710288320,
            "fechaActuacion": "2026-05-15T00:00:00",
            "actuacion": "Al despacho",
            "anotacion": None,
            "fechaInicial": None,
            "fechaFinal": None,
            "fechaRegistro": "2026-05-15T00:00:00",
        },
        {
            "idRegActuacion": 2702295560,
            "fechaActuacion": "2026-04-29T00:00:00",
            "actuacion": "Recepción memorial",
            "anotacion": "ALLEGAN RECURSO/OR",
            "fechaInicial": None,
            "fechaFinal": None,
            "fechaRegistro": "2026-04-29T00:00:00",
        },
    ]
}
DETALLE = {"ultimaActualizacion": "2026-10-08T08:29:32.06"}


class RespuestaFalsa:
    def __init__(self, status=200, datos=None, json_invalido=False):
        self.status_code = status
        self.datos = datos
        self.json_invalido = json_invalido

    def json(self):
        if self.json_invalido:
            raise ValueError("no es JSON")
        return self.datos


class SesionFalsa:
    """Responde según un fragmento de la URL. Una lista se consume de a una respuesta."""

    def __init__(self, rutas):
        self.rutas = rutas
        self.llamadas = []

    def get(self, url, params=None, timeout=None):
        self.llamadas.append((url, params))
        for fragmento, resp in self.rutas.items():
            if fragmento in url:
                if isinstance(resp, list):
                    resp = resp.pop(0)
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"llamada no esperada: {url}")


def crear(rutas, reintentos=3):
    dormidos = []
    sesion = SesionFalsa(rutas)
    f = Fetcher(sesion=sesion, pausa=1.0, reintentos=reintentos, espera=2.0, dormir=dormidos.append)
    return f, sesion, dormidos


def rutas_ok():
    return {
        "NumeroRadicacion": RespuestaFalsa(200, BUSQUEDA),
        "Actuaciones": RespuestaFalsa(200, ACTUACIONES),
        "Detalle": RespuestaFalsa(200, DETALLE),
    }


def test_consulta_exitosa_devuelve_actuaciones_normalizadas():
    f, sesion, _ = crear(rutas_ok())
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.id_proceso == 108832900
    assert c.despacho == "JUZGADO 077 CIVIL MUNICIPAL DE BOGOTÁ"
    assert c.ultima_actualizacion == "2026-10-08T08:29:32.06"
    a = c.actuaciones[0]
    assert (a.id_reg_actuacion, a.fecha_actuacion, a.actuacion, a.anotacion) == (
        2710288320,
        "2026-05-15",
        "Al despacho",
        "",
    )
    assert c.actuaciones[1].anotacion == "ALLEGAN RECURSO/OR"


def test_siempre_pide_solo_activos_false():
    f, sesion, _ = crear(rutas_ok())
    f.consultar(RAD)
    url, params = sesion.llamadas[0]
    assert params["SoloActivos"] == "false"
    assert params["numero"] == RAD.radicado


def test_busqueda_vacia_es_sin_resultados_y_cuenta_para_r5():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, {"procesos": []})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA
    assert c.motivo == "sin resultados"
    assert c.falla_portal is True


def test_radicado_invalido_no_llama_al_portal():
    f, sesion, _ = crear(rutas_ok())
    c = f.consultar(Radicado("123"))
    assert c.estado == FALLIDA
    assert "23 dígitos" in c.motivo
    assert c.falla_portal is False
    assert sesion.llamadas == []


def test_actuaciones_404_es_proceso_sin_actuaciones():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, {"StatusCode": 404, "Message": "No se encontraron Actuaciones para el Proceso: 108832900"})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.actuaciones == ()


def test_reintenta_con_espera_creciente_y_se_recupera():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = [RespuestaFalsa(500), RespuestaFalsa(200, BUSQUEDA)]
    f, _, dormidos = crear(rutas)
    assert f.consultar(RAD).estado == EXITOSA
    assert dormidos == [2.0]


def test_portal_caido_agota_reintentos_y_cuenta_como_falla():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = requests.Timeout("lento")
    f, sesion, dormidos = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA
    assert c.falla_portal is True
    assert "Timeout" in c.motivo
    assert len(sesion.llamadas) == 3
    assert dormidos == [2.0, 4.0]


def test_respuesta_que_no_es_json_se_reintenta():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, json_invalido=True)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def test_forma_inesperada_es_error():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(200, {"otra_cosa": []})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == ERROR
    assert c.falla_portal is True


def test_falla_del_detalle_no_tumba_la_consulta():
    rutas = rutas_ok()
    rutas["Detalle"] = RespuestaFalsa(500)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA
    assert c.ultima_actualizacion == ""


def test_pausar_duerme_el_tiempo_configurado():
    f, _, dormidos = crear(rutas_ok())
    f.pausar()
    assert dormidos == [1.0]


def test_la_sesion_por_defecto_se_identifica_y_no_usa_el_user_agent_de_requests():
    f = Fetcher()
    assert f.sesion.headers["User-Agent"] == USER_AGENT
    assert not USER_AGENT.startswith("python-requests")


def test_404_sin_el_mensaje_esperado_es_falla_del_portal():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, {"StatusCode": 404, "Message": "Otra cosa"})
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def test_404_con_cuerpo_ilegible_es_falla_del_portal():
    rutas = rutas_ok()
    rutas["Actuaciones"] = RespuestaFalsa(404, json_invalido=True)
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA and c.falla_portal is True


def _pagina(ids, cant):
    return RespuestaFalsa(
        200,
        {
            "actuaciones": [
                {
                    "idRegActuacion": i,
                    "fechaActuacion": "2026-05-15T00:00:00",
                    "actuacion": "x",
                    "cant": cant,
                }
                for i in ids
            ]
        },
    )


def test_pide_mas_paginas_hasta_completar_el_total():
    rutas = rutas_ok()
    rutas["Actuaciones"] = [_pagina([3, 2], cant=3), _pagina([1], cant=3)]
    f, sesion, _ = crear(rutas)
    c = f.consultar(RAD)
    assert [a.id_reg_actuacion for a in c.actuaciones] == [3, 2, 1]
    paginas = [p["pagina"] for u, p in sesion.llamadas if "Actuaciones" in u]
    assert paginas == [1, 2]


def test_varios_procesos_para_un_radicado_se_unen_sin_duplicar():
    rutas = rutas_ok()
    busqueda = {"procesos": [{"idProceso": 1, "despacho": "A"}, {"idProceso": 2, "despacho": "B"}]}
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, busqueda)
    rutas["Actuaciones"] = [_pagina([5, 4], cant=2), _pagina([4, 9], cant=2)]
    f, _, _ = crear(rutas)
    c = f.consultar(RAD)
    assert c.id_proceso == 1 and c.despacho == "A"
    assert sorted(a.id_reg_actuacion for a in c.actuaciones) == [4, 5, 9]


def _busqueda_con(cuerpo):
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = RespuestaFalsa(200, cuerpo)
    f, _, _ = crear(rutas)
    return f.consultar(RAD)


def test_clave_renombrada_en_la_busqueda_es_error_no_sin_resultados():
    c = _busqueda_con({"resultados": []})
    assert c.estado == ERROR and c.falla_portal is True


def test_proceso_sin_id_proceso_es_error():
    c = _busqueda_con({"procesos": [{"despacho": "A"}]})
    assert c.estado == ERROR


def test_busqueda_con_cuerpo_lista_es_error():
    c = _busqueda_con([])
    assert c.estado == ERROR


def crear_con(rutas, **kw):
    dormidos = []
    sesion = SesionFalsa(rutas)
    f = Fetcher(sesion=sesion, pausa=1.0, reintentos=3, espera=2.0, dormir=dormidos.append, **kw)
    return f, sesion, dormidos


def test_pausa_entre_peticiones_no_espera_antes_de_la_primera():
    f, sesion, dormidos = crear_con(rutas_ok(), pausa_peticiones=1.5)
    assert f.consultar(RAD).estado == EXITOSA
    assert len(sesion.llamadas) == 3
    assert dormidos == [1.5, 1.5]


def test_sin_consultar_detalle_no_pide_detalle():
    f, sesion, _ = crear_con(rutas_ok(), consultar_detalle=False)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA and c.ultima_actualizacion == ""
    assert not any("Detalle" in u for u, _ in sesion.llamadas)


def test_403_persistente_es_bloqueo_con_esperas_largas():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = [RespuestaFalsa(403)] * 3
    f, sesion, dormidos = crear_con(rutas)
    c = f.consultar(RAD)
    assert c.estado == FALLIDA
    assert c.bloqueo is True and c.falla_portal is True
    assert c.motivo == "HTTP 403: el portal bloqueó las consultas"
    assert dormidos == [30.0, 60.0]
    assert len([u for u, _ in sesion.llamadas if "NumeroRadicacion" in u]) == 3


def test_403_que_se_recupera_devuelve_exito():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = [RespuestaFalsa(403), RespuestaFalsa(200, BUSQUEDA)]
    f, _, dormidos = crear_con(rutas)
    c = f.consultar(RAD)
    assert c.estado == EXITOSA and c.bloqueo is False
    assert dormidos == [30.0]


def test_429_se_trata_como_bloqueo():
    rutas = rutas_ok()
    rutas["NumeroRadicacion"] = [RespuestaFalsa(429)] * 3
    f, _, dormidos = crear_con(rutas)
    c = f.consultar(RAD)
    assert c.bloqueo is True
    assert c.motivo.startswith("HTTP 429")
    assert dormidos == [30.0, 60.0]


def test_403_solo_en_el_detalle_tambien_es_bloqueo():
    rutas = rutas_ok()
    rutas["Detalle"] = [RespuestaFalsa(403)] * 3
    f, _, _ = crear_con(rutas, consultar_detalle=True)
    c = f.consultar(RAD)
    assert c.bloqueo is True and c.estado == FALLIDA


def test_pausar_con_cancelado_verdadero_lanza_sin_dormir():
    dormidos = []
    f = Fetcher(sesion=SesionFalsa({}), pausa=60.0, dormir=dormidos.append, cancelado=lambda: True)
    with pytest.raises(CicloCancelado):
        f.pausar()
    assert dormidos == []


def test_una_espera_larga_se_corta_en_tramos_de_un_segundo_al_cancelar():
    dormidos, llamadas = [], []

    def cancelado():
        llamadas.append(1)
        return len(llamadas) > 2

    f = Fetcher(sesion=SesionFalsa({}), pausa=60.0, dormir=dormidos.append, cancelado=cancelado)
    with pytest.raises(CicloCancelado):
        f.pausar()
    assert dormidos == [1.0, 1.0]


def test_sin_cancelado_la_espera_es_un_solo_dormir():
    f, _, dormidos = crear(rutas_ok())
    f.pausar()
    assert dormidos == [1.0]


def test_cancelar_durante_la_espera_de_un_bloqueo_interrumpe_la_consulta():
    rutas = {"NumeroRadicacion": [RespuestaFalsa(403, {})] * 5}
    dormidos, llamadas = [], []

    def cancelado():
        llamadas.append(1)
        return len(llamadas) > 3

    f = Fetcher(sesion=SesionFalsa(rutas), dormir=dormidos.append, cancelado=cancelado, espera_bloqueo=30.0)
    with pytest.raises(CicloCancelado):
        f.consultar(Radicado("11001400307720210114700"))
    assert dormidos and all(d <= 1.0 for d in dormidos)
