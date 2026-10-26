"""Proceso periódico (cron cada 5 minutos): `python -m app.trabajador`.

1. Crea un recordatorio por cada solicitud abierta con el seguimiento vencido.
   La clave (solicitud, tipo, vencimiento) es única: correrlo dos veces no
   duplica nada (escenario 8), y una fecha nueva permite un recordatorio nuevo.
2. Recupera los trabajos bloqueados en `en_proceso` más allá del tiempo límite.
3. Reclama y envía los trabajos pendientes, con reintentos limitados.
"""

import logging
import sqlite3
from datetime import timedelta

from app.config import ajustes
from app.correo import Enviador, EnviadorMemoria, EnviadorSMTP, ErrorPermanente, ResultadoAmbiguo
from app.db import conectar, inicializar, transaccion
from app.reloj import Reloj, iso

log = logging.getLogger("pyme.trabajador")

MAX_INTENTOS = 3
# Reintentos a 1 y 5 minutos después de un fallo (ESPECIFICACION.md).
ESPERAS_REINTENTO = [timedelta(minutes=1), timedelta(minutes=5)]
LIMITE_BLOQUEO = timedelta(minutes=10)


def crear_recordatorios(con: sqlite3.Connection, reloj: Reloj) -> int:
    ahora = iso(reloj.ahora())
    with transaccion(con):
        cur = con.execute(
            """INSERT OR IGNORE INTO trabajos (solicitud_id, tipo, vencimiento, clave, proxima_ejecucion)
               SELECT id, 'recordatorio', vence_en, id || ':recordatorio:' || vence_en, ?
               FROM solicitudes
               WHERE estado NOT IN ('ganada', 'perdida') AND vence_en IS NOT NULL AND vence_en <= ?""",
            (ahora, ahora),
        )
        return cur.rowcount


def recuperar_bloqueados(con: sqlite3.Connection, reloj: Reloj) -> int:
    """Un trabajo que quedó `en_proceso` (el proceso murió a mitad) no se reintenta
    a ciegas: pudo haberse enviado. Queda fallido y visible para revisión."""
    with transaccion(con):
        cur = con.execute(
            """UPDATE trabajos SET estado = 'fallido', ultimo_error = 'interrumpido durante el envío: revisar'
               WHERE estado = 'en_proceso' AND bloqueado_hasta < ?""",
            (iso(reloj.ahora()),),
        )
        return cur.rowcount


def _reclamar(con: sqlite3.Connection, reloj: Reloj) -> sqlite3.Row | None:
    ahora = reloj.ahora()
    with transaccion(con):
        t = con.execute(
            "SELECT * FROM trabajos WHERE estado = 'pendiente' AND proxima_ejecucion <= ? ORDER BY proxima_ejecucion LIMIT 1",
            (iso(ahora),),
        ).fetchone()
        if t is None:
            return None
        con.execute(
            "UPDATE trabajos SET estado = 'en_proceso', intentos = intentos + 1, bloqueado_hasta = ? WHERE id = ?",
            (iso(ahora + LIMITE_BLOQUEO), t["id"]),
        )
        return con.execute("SELECT * FROM trabajos WHERE id = ?", (t["id"],)).fetchone()


def _sigue_vigente(con: sqlite3.Connection, t: sqlite3.Row, reloj: Reloj) -> bool:
    """Justo antes de enviar un recordatorio se vuelve a mirar la solicitud: si se
    cerró o cambió su fecha mientras esperaba, el aviso es obsoleto (escenario 11)."""
    if t["tipo"] != "recordatorio":
        return True
    s = con.execute("SELECT estado, vence_en FROM solicitudes WHERE id = ?", (t["solicitud_id"],)).fetchone()
    return (
        s["estado"] not in ("ganada", "perdida")
        and s["vence_en"] == t["vencimiento"]
        and s["vence_en"] <= iso(reloj.ahora())
    )


def _mensaje(con: sqlite3.Connection, t: sqlite3.Row) -> tuple[str, str, str] | None:
    s = con.execute(
        """SELECT s.*, u.email AS email_responsable, u.nombre AS nombre_responsable
           FROM solicitudes s LEFT JOIN usuarios u ON u.id = s.responsable_id WHERE s.id = ?""",
        (t["solicitud_id"],),
    ).fetchone()
    if t["tipo"] == "confirmacion":
        return (
            s["email"],
            f"Recibimos tu solicitud de presupuesto - {ajustes.nombre_empresa}",
            f"Hola {s['nombre']}:\n\nRecibimos tu solicitud y te contactaremos pronto.\n"
            f"Tu número de solicitud es {s['id']}.\n\n{ajustes.nombre_empresa}",
        )
    if s["email_responsable"] is None:
        return None
    if t["tipo"] == "recordatorio":
        return (
            s["email_responsable"],
            f"Seguimiento pendiente: solicitud {s['id']}",
            f"La solicitud {s['id']} ({s['nombre']}) tiene el seguimiento vencido desde {t['vencimiento']} (UTC).\n"
            "Registra una actuación en el panel.",
        )
    return (
        s["email_responsable"],
        f"No se pudo enviar un correo de la solicitud {s['id']}",
        f"Un envío asociado a la solicitud {s['id']} falló y requiere revisión en el panel.",
    )


def _fallar(con: sqlite3.Connection, reloj: Reloj, t: sqlite3.Row, error: str, reintentable: bool) -> None:
    ahora = reloj.ahora()
    with transaccion(con):
        if reintentable and t["intentos"] < MAX_INTENTOS:
            espera = ESPERAS_REINTENTO[t["intentos"] - 1]
            con.execute(
                "UPDATE trabajos SET estado = 'pendiente', ultimo_error = ?, proxima_ejecucion = ?, bloqueado_hasta = NULL WHERE id = ?",
                (error, iso(ahora + espera), t["id"]),
            )
            return
        con.execute(
            "UPDATE trabajos SET estado = 'fallido', ultimo_error = ?, bloqueado_hasta = NULL WHERE id = ?",
            (error, t["id"]),
        )
        # Se avisa al responsable, salvo que lo que falló sea justamente un aviso.
        if t["tipo"] != "aviso_fallo":
            con.execute(
                "INSERT OR IGNORE INTO trabajos (solicitud_id, tipo, clave, proxima_ejecucion) VALUES (?, 'aviso_fallo', ?, ?)",
                (t["solicitud_id"], f"{t['solicitud_id']}:aviso_fallo:{t['id']}", iso(ahora)),
            )


def procesar_pendientes(con: sqlite3.Connection, reloj: Reloj, enviador: Enviador, limite: int = 100) -> int:
    procesados = 0
    while procesados < limite and (t := _reclamar(con, reloj)) is not None:
        procesados += 1
        if not _sigue_vigente(con, t, reloj):
            con.execute(
                "UPDATE trabajos SET estado = 'cancelado', bloqueado_hasta = NULL WHERE id = ?", (t["id"],)
            )
            continue
        mensaje = _mensaje(con, t)
        if mensaje is None:
            _fallar(con, reloj, t, "sin responsable asignado", reintentable=False)
            continue
        try:
            id_proveedor = enviador.enviar(*mensaje)
        except ErrorPermanente as e:
            _fallar(con, reloj, t, f"error permanente: {e}", reintentable=False)
        except ResultadoAmbiguo as e:
            _fallar(con, reloj, t, f"resultado ambiguo, revisar antes de reenviar: {e}", reintentable=False)
        except Exception as e:  # transitorio o desconocido: se reintenta con límite
            # Solo el tipo de error al log: nunca el cuerpo, que trae datos personales.
            log.warning("Fallo de envío del trabajo %s: %s", t["id"], type(e).__name__)
            _fallar(con, reloj, t, f"error transitorio: {type(e).__name__}", reintentable=True)
        else:
            con.execute(
                "UPDATE trabajos SET estado = 'enviado', enviado_en = ?, id_proveedor = ?, bloqueado_hasta = NULL, ultimo_error = NULL WHERE id = ?",
                (iso(reloj.ahora()), id_proveedor, t["id"]),
            )
    return procesados


def ejecutar(con: sqlite3.Connection, reloj: Reloj, enviador: Enviador) -> dict:
    return {
        "recordatorios_creados": crear_recordatorios(con, reloj),
        "recuperados": recuperar_bloqueados(con, reloj),
        "procesados": procesar_pendientes(con, reloj, enviador),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    inicializar(ajustes.db_path)
    con = conectar(ajustes.db_path)
    reloj = Reloj()
    enviador = EnviadorSMTP() if ajustes.correo_modo == "smtp" else EnviadorMemoria(con, reloj)
    log.info("Trabajador: %s", ejecutar(con, reloj, enviador))


if __name__ == "__main__":
    main()
