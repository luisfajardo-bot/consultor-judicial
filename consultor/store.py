import sqlite3
from datetime import datetime
from pathlib import Path

from .models import (
    CONFIRMADA,
    DESCARTADA,
    EXITOSA,
    PENDIENTE,
    POSIBLE_NOVEDAD,
    Consulta,
    Radicado,
    Veredicto,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS radicado (
    radicado TEXT PRIMARY KEY, empresa TEXT, despacho TEXT, id_proceso INTEGER);
CREATE TABLE IF NOT EXISTS actuacion (
    id_reg_actuacion INTEGER PRIMARY KEY, radicado TEXT NOT NULL,
    fecha_actuacion TEXT, actuacion TEXT, anotacion TEXT, fecha_registro TEXT,
    fecha_inicial TEXT, fecha_final TEXT, primera_vez_visto TEXT);
DROP INDEX IF EXISTS ix_actuacion_radicado;
CREATE INDEX IF NOT EXISTS ix_actuacion_radicado_fecha
    ON actuacion(radicado, fecha_actuacion DESC, id_reg_actuacion DESC);
CREATE TABLE IF NOT EXISTS ciclo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT NOT NULL, fin TEXT,
    estado TEXT NOT NULL, parcial INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS consulta (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ciclo_id INTEGER NOT NULL,
    radicado TEXT NOT NULL, hora TEXT NOT NULL, estado TEXT NOT NULL,
    resultado TEXT NOT NULL, motivo TEXT, despacho TEXT, ultima_actualizacion TEXT,
    UNIQUE (ciclo_id, radicado));
CREATE INDEX IF NOT EXISTS ix_consulta_radicado ON consulta(radicado, estado);
CREATE TABLE IF NOT EXISTS alerta (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ciclo_id INTEGER NOT NULL,
    radicado TEXT NOT NULL, id_reg_actuacion INTEGER NOT NULL UNIQUE,
    anterior TEXT, estado TEXT NOT NULL, validada_por TEXT, validada_en TEXT);
CREATE INDEX IF NOT EXISTS ix_alerta_ciclo ON alerta(ciclo_id);
CREATE INDEX IF NOT EXISTS ix_alerta_pendiente ON alerta(id) WHERE estado = 'Pendiente';
"""

CONSULTAS_SQL = """
SELECT c.radicado, c.estado, c.resultado, c.motivo, c.hora,
       COALESCE(NULLIF(c.despacho, ''), r.despacho, '') AS despacho,
       r.empresa AS empresa
FROM consulta c JOIN radicado r ON r.radicado = c.radicado
WHERE c.ciclo_id = ? ORDER BY c.id
"""

ALERTAS_SQL = """
SELECT a.id, a.radicado, a.anterior, a.estado, a.validada_por, a.validada_en,
       t.fecha_actuacion, t.actuacion, t.anotacion
FROM alerta a JOIN actuacion t ON t.id_reg_actuacion = a.id_reg_actuacion
WHERE a.ciclo_id = ? ORDER BY a.id
"""

PENDIENTES_SQL = """
SELECT a.id, a.radicado, a.ciclo_id, a.anterior, a.estado,
       t.fecha_actuacion, t.actuacion, t.anotacion,
       r.empresa AS empresa,
       COALESCE(NULLIF(c.despacho, ''), r.despacho, '') AS despacho,
       c.hora AS hora
FROM alerta a
JOIN actuacion t ON t.id_reg_actuacion = a.id_reg_actuacion
JOIN radicado r ON r.radicado = a.radicado
LEFT JOIN consulta c ON c.ciclo_id = a.ciclo_id AND c.radicado = a.radicado
WHERE a.estado = 'Pendiente' AND a.ciclo_id <> ?
ORDER BY a.id
"""


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


class Store:
    def __init__(self, ruta):
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(ruta))
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        if "parcial" not in {f["name"] for f in self.con.execute("PRAGMA table_info(ciclo)")}:
            with self.con:
                self.con.execute("ALTER TABLE ciclo ADD COLUMN parcial INTEGER NOT NULL DEFAULT 0")

    # ciclos
    def iniciar_ciclo(self, ahora: datetime, parcial: bool = False) -> int:
        """Continúa el ciclo abierto o pausado del mismo día si existe (reanudación)."""
        fila = self.con.execute(
            "SELECT id FROM ciclo WHERE (estado = 'En curso' OR estado LIKE 'Pausado%') "
            "AND substr(inicio, 1, 10) = ? AND parcial = ?",
            (ahora.date().isoformat(), int(parcial)),
        ).fetchone()
        if fila:
            with self.con:
                self.con.execute(
                    "UPDATE ciclo SET estado = 'En curso', fin = NULL WHERE id = ?", (fila["id"],)
                )
            return fila["id"]
        with self.con:
            cur = self.con.execute(
                "INSERT INTO ciclo (inicio, estado, parcial) VALUES (?, 'En curso', ?)",
                (_iso(ahora), int(parcial)),
            )
        return cur.lastrowid

    def cerrar_interrumpidos(self, ahora: datetime) -> int:
        """Marca Interrumpido los ciclos abiertos de días anteriores."""
        with self.con:
            cur = self.con.execute(
                "UPDATE ciclo SET estado = 'Interrumpido', fin = ? "
                "WHERE (estado = 'En curso' OR estado LIKE 'Pausado%') AND substr(inicio, 1, 10) <> ?",
                (_iso(ahora), ahora.date().isoformat()),
            )
        return cur.rowcount

    def pendientes(self, ciclo_id: int, total: int) -> int:
        """Radicados de la lista que aún no tienen consulta registrada en el ciclo."""
        n = self.con.execute(
            "SELECT COUNT(*) FROM consulta WHERE ciclo_id = ?", (ciclo_id,)
        ).fetchone()[0]
        return total - n

    def ultimo_cierre(self) -> datetime | None:
        f = self.con.execute("SELECT MAX(fin) AS fin FROM ciclo WHERE fin IS NOT NULL AND parcial = 0").fetchone()
        return datetime.fromisoformat(f["fin"]) if f["fin"] else None

    def cerrar_ciclo(self, ciclo_id: int, estado: str, ahora: datetime) -> None:
        with self.con:
            self.con.execute(
                "UPDATE ciclo SET fin = ?, estado = ? WHERE id = ?",
                (_iso(ahora), estado, ciclo_id),
            )

    # lectura
    def registrar_radicado(self, r: Radicado) -> None:
        self.registrar_radicados([r])

    def registrar_radicados(self, radicados) -> None:
        with self.con:
            self.con.executemany(
                "INSERT INTO radicado (radicado, empresa, despacho) VALUES (?, ?, ?) "
                "ON CONFLICT(radicado) DO UPDATE SET "
                "empresa = excluded.empresa, despacho = excluded.despacho",
                [(r.radicado, r.empresa, r.despacho) for r in radicados],
            )

    def ya_consultado(self, ciclo_id: int, radicado: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM consulta WHERE ciclo_id = ? AND radicado = ?",
                (ciclo_id, radicado),
            ).fetchone()
            is not None
        )

    def ids_conocidos(self, radicado: str) -> set[int]:
        filas = self.con.execute(
            "SELECT id_reg_actuacion FROM actuacion WHERE radicado = ?", (radicado,)
        )
        return {f["id_reg_actuacion"] for f in filas}

    def tiene_referencia(self, radicado: str) -> bool:
        return (
            self.con.execute(
                "SELECT 1 FROM consulta WHERE radicado = ? AND estado = ? LIMIT 1",
                (radicado, EXITOSA),
            ).fetchone()
            is not None
        )

    def ultima_actuacion(self, radicado: str) -> str:
        f = self.con.execute(
            "SELECT fecha_actuacion, actuacion FROM actuacion WHERE radicado = ? "
            "ORDER BY fecha_actuacion DESC, id_reg_actuacion DESC LIMIT 1",
            (radicado,),
        ).fetchone()
        return f"{f['fecha_actuacion']}: {f['actuacion']}" if f else ""

    # escritura
    def registrar_resultado(
        self,
        ciclo_id: int,
        radicado: str,
        consulta: Consulta,
        veredicto: Veredicto,
        anterior: str,
        ahora: datetime,
    ) -> None:
        """Guarda actuaciones, consulta y alertas en una sola transacción.

        Si el proceso se cae a la mitad no queda una actuación conocida sin su alerta.
        """
        hora = _iso(ahora)
        with self.con:
            if consulta.estado == EXITOSA:
                self.con.executemany(
                    "INSERT OR IGNORE INTO actuacion (id_reg_actuacion, radicado, "
                    "fecha_actuacion, actuacion, anotacion, fecha_registro, "
                    "fecha_inicial, fecha_final, primera_vez_visto) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            a.id_reg_actuacion,
                            radicado,
                            a.fecha_actuacion,
                            a.actuacion,
                            a.anotacion,
                            a.fecha_registro,
                            a.fecha_inicial,
                            a.fecha_final,
                            hora,
                        )
                        for a in consulta.actuaciones
                    ],
                )
                if consulta.id_proceso:
                    self.con.execute(
                        "UPDATE radicado SET id_proceso = ? WHERE radicado = ?",
                        (consulta.id_proceso, radicado),
                    )
            self.con.execute(
                "INSERT INTO consulta (ciclo_id, radicado, hora, estado, resultado, "
                "motivo, despacho, ultima_actualizacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ciclo_id,
                    radicado,
                    hora,
                    consulta.estado,
                    veredicto.resultado,
                    veredicto.motivo,
                    consulta.despacho,
                    consulta.ultima_actualizacion,
                ),
            )
            self.con.executemany(
                "INSERT OR IGNORE INTO alerta (ciclo_id, radicado, id_reg_actuacion, "
                "anterior, estado) VALUES (?, ?, ?, ?, ?)",
                [
                    (ciclo_id, radicado, a.id_reg_actuacion, anterior, PENDIENTE)
                    for a in veredicto.nuevas
                ],
            )

    def registrar_decision(
        self, alerta_id: int, estado: str, usuario: str, ahora: datetime
    ) -> bool:
        """Única puerta de escritura de decisiones. Solo cambia alertas Pendiente."""
        if estado not in (CONFIRMADA, DESCARTADA):
            raise ValueError(f"decisión inválida: {estado!r}")
        with self.con:
            cur = self.con.execute(
                "UPDATE alerta SET estado = ?, validada_por = ?, validada_en = ? "
                "WHERE id = ? AND estado = ?",
                (estado, usuario, _iso(ahora), alerta_id, PENDIENTE),
            )
        return cur.rowcount == 1

    # salida
    def resumen(self, ciclo_id: int) -> dict:
        f = self.con.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(estado = ?), 0) AS exitosas, "
            "COALESCE(SUM(resultado = ?), 0) AS novedades "
            "FROM consulta WHERE ciclo_id = ?",
            (EXITOSA, POSIBLE_NOVEDAD, ciclo_id),
        ).fetchone()
        return {
            "total": f["total"],
            "exitosas": f["exitosas"],
            "fallidas": f["total"] - f["exitosas"],
            "novedades": f["novedades"],
        }

    def filas_reporte(self, ciclo_id: int) -> list[dict]:
        alertas: dict[str, list] = {}
        for a in self.con.execute(ALERTAS_SQL, (ciclo_id,)):
            alertas.setdefault(a["radicado"], []).append(a)
        filas = []
        for c in self.con.execute(CONSULTAS_SQL, (ciclo_id,)):
            base = {
                "alerta_id": None,
                "empresa": c["empresa"] or "",
                "radicado": c["radicado"],
                "despacho": c["despacho"] or "",
                "estado_consulta": c["estado"],
                "resultado": c["resultado"],
                "anterior": "",
                "fecha_detectada": "",
                "detectada": "",
                "anotacion": "",
                "hora": c["hora"],
                "motivo": c["motivo"] or "",
                "decision": "",
                "validada_por": "",
                "validada_en": "",
            }
            if c["resultado"] == POSIBLE_NOVEDAD:
                for a in alertas.get(c["radicado"], []):
                    filas.append(
                        {
                            **base,
                            "alerta_id": a["id"],
                            "anterior": a["anterior"] or "",
                            "fecha_detectada": a["fecha_actuacion"],
                            "detectada": a["actuacion"],
                            "anotacion": a["anotacion"] or "",
                            "decision": a["estado"],
                            "validada_por": a["validada_por"] or "",
                            "validada_en": a["validada_en"] or "",
                        }
                    )
            else:
                filas.append(base)
        for a in self.con.execute(PENDIENTES_SQL, (ciclo_id,)):
            filas.append(
                {
                    "alerta_id": a["id"],
                    "empresa": a["empresa"] or "",
                    "radicado": a["radicado"],
                    "despacho": a["despacho"] or "",
                    "estado_consulta": "Exitosa",
                    "resultado": POSIBLE_NOVEDAD,
                    "anterior": a["anterior"] or "",
                    "fecha_detectada": a["fecha_actuacion"],
                    "detectada": a["actuacion"],
                    "anotacion": a["anotacion"] or "",
                    "hora": a["hora"] or "",
                    "motivo": f"alerta pendiente del ciclo {a['ciclo_id']}",
                    "decision": a["estado"],
                    "validada_por": "",
                    "validada_en": "",
                }
            )
        return filas
