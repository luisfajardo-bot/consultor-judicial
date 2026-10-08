import re
import time

import requests

from .models import ERROR, EXITOSA, FALLIDA, Actuacion, Consulta, Radicado

BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"
USER_AGENT = "ConsultorJudicial/1.0 (Gerencia Juridica; consulta de procesos propios)"
MAX_PAGINAS = 20
RADICADO_RE = re.compile(r"^\d{23}$")


class ErrorPortal(Exception):
    """El portal no respondió bien tras agotar los reintentos."""


def _fecha(valor) -> str:
    return (valor or "")[:10]


def _sin_actuaciones(datos) -> bool:
    return isinstance(datos, dict) and "No se encontraron" in str(datos.get("Message", ""))


def _actuacion(a: dict, radicado: str) -> Actuacion:
    return Actuacion(
        id_reg_actuacion=a["idRegActuacion"],
        radicado=radicado,
        fecha_actuacion=_fecha(a["fechaActuacion"]),
        actuacion=(a.get("actuacion") or "").strip(),
        anotacion=(a.get("anotacion") or "").strip(),
        fecha_registro=_fecha(a.get("fechaRegistro")),
        fecha_inicial=_fecha(a.get("fechaInicial")),
        fecha_final=_fecha(a.get("fechaFinal")),
    )


class Fetcher:
    """Único módulo que conoce la Rama Judicial. Descarta sujetosProcesales (datos personales)."""

    def __init__(
        self,
        sesion=None,
        pausa=1.0,
        reintentos=3,
        espera=2.0,
        timeout=30,
        dormir=time.sleep,
    ):
        if sesion is None:
            sesion = requests.Session()
            sesion.headers["User-Agent"] = USER_AGENT
        self.sesion = sesion
        self.pausa = pausa
        self.reintentos = reintentos
        self.espera = espera
        self.timeout = timeout
        self.dormir = dormir

    def pausar(self) -> None:
        self.dormir(self.pausa)

    def _get(self, url, params=None):
        """GET con reintentos y espera creciente. Un 404 no se reintenta."""
        motivo = ""
        for intento in range(self.reintentos):
            try:
                resp = self.sesion.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                motivo = type(e).__name__
            else:
                if resp.status_code == 404:
                    try:
                        return 404, resp.json()
                    except ValueError:
                        return 404, None
                if resp.status_code == 200:
                    try:
                        return 200, resp.json()
                    except ValueError:
                        motivo = "respuesta que no es JSON"
                else:
                    motivo = f"HTTP {resp.status_code}"
            if intento < self.reintentos - 1:
                self.dormir(self.espera * (2**intento))
        raise ErrorPortal(motivo)

    def _actuaciones(self, id_proceso, radicado) -> list[Actuacion]:
        acumuladas: list[Actuacion] = []
        pagina = 1
        while True:
            estado, datos = self._get(
                f"{BASE}/Proceso/Actuaciones/{id_proceso}", {"pagina": pagina}
            )
            if estado == 404:
                if pagina == 1 and not _sin_actuaciones(datos):
                    raise ErrorPortal("404 inesperado al pedir actuaciones")
                break
            lista = datos["actuaciones"]
            acumuladas.extend(_actuacion(a, radicado) for a in lista)
            total = max((a.get("cant") or 0 for a in lista), default=0)
            if not lista or len(acumuladas) >= total:
                break
            pagina += 1
            if pagina > MAX_PAGINAS:
                raise ErrorPortal(f"más de {MAX_PAGINAS} páginas de actuaciones")
        return acumuladas

    def _ultima_actualizacion(self, id_proceso) -> str:
        try:
            estado, datos = self._get(f"{BASE}/Proceso/Detalle/{id_proceso}")
        except ErrorPortal:
            return ""
        if estado != 200 or not isinstance(datos, dict):
            return ""
        return datos.get("ultimaActualizacion") or ""

    def consultar(self, r: Radicado) -> Consulta:
        if not RADICADO_RE.match(r.radicado):
            return Consulta(FALLIDA, motivo="radicado inválido: debe tener 23 dígitos")
        try:
            estado, datos = self._get(
                f"{BASE}/Procesos/Consulta/NumeroRadicacion",
                {"numero": r.radicado, "SoloActivos": "false", "pagina": 1},
            )
            procesos = (datos or {}).get("procesos") or []
            if estado == 404 or not procesos:
                return Consulta(FALLIDA, motivo="sin resultados")
            primero = procesos[0]
            id_proceso = primero["idProceso"]
            vistas: dict[int, Actuacion] = {}
            for p in procesos:
                for a in self._actuaciones(p["idProceso"], r.radicado):
                    vistas.setdefault(a.id_reg_actuacion, a)
            return Consulta(
                EXITOSA,
                id_proceso=id_proceso,
                despacho=(primero.get("despacho") or "").strip(),
                ultima_actualizacion=self._ultima_actualizacion(id_proceso),
                actuaciones=tuple(vistas.values()),
            )
        except ErrorPortal as e:
            return Consulta(FALLIDA, motivo=str(e), falla_portal=True)
        except (KeyError, TypeError, AttributeError) as e:
            return Consulta(
                ERROR,
                motivo=f"respuesta inesperada: {type(e).__name__} {e}",
                falla_portal=True,
            )
