"""Reglas del proceso (ESPECIFICACION.md, § Estados y reglas). Sin HTTP: la web y
las pruebas llaman a estas funciones."""

import sqlite3
from datetime import datetime, timedelta

from email_validator import EmailNotValidError, validate_email

from app.config import ajustes
from app.db import transaccion
from app.reloj import Reloj, iso

ESTADOS = ("nueva", "contactada", "presupuesto_enviado", "ganada", "perdida")
FINALES = ("ganada", "perdida")
TRANSICIONES = {
    "nueva": {"contactada", "perdida"},
    "contactada": {"presupuesto_enviado", "ganada", "perdida"},
    "presupuesto_enviado": {"ganada", "perdida"},
    "ganada": set(),
    "perdida": set(),
}
# Tipos de actuación. Una nota interna no es contacto: no mueve el vencimiento.
TIPOS_ACTUACION = {"nota": False, "llamada": True, "correo": True, "reunion": True, "presupuesto": True}
LARGOS = {"nombre": 120, "email": 254, "telefono": 30, "descripcion": 4000, "origen": 80}


class ErrorValidacion(Exception):
    def __init__(self, errores: dict[str, str]):
        super().__init__(", ".join(errores.values()))
        self.errores = errores


def validar_solicitud(datos: dict) -> dict:
    """Limpia y valida los datos del formulario público. Lanza ErrorValidacion."""
    limpio = {
        k: (str(datos.get(k) or "")).strip() for k in (*LARGOS, "utm_source", "utm_medium", "utm_campaign")
    }
    errores = {}
    for campo in ("nombre", "email", "descripcion"):
        if not limpio[campo]:
            errores[campo] = "Este campo es obligatorio."
    for campo, largo in LARGOS.items():
        if len(limpio[campo]) > largo:
            errores[campo] = f"Máximo {largo} caracteres."
    if limpio["email"] and "email" not in errores:
        try:
            limpio["email"] = validate_email(limpio["email"], check_deliverability=False).normalized
        except EmailNotValidError:
            errores["email"] = "El email no es válido."
    if errores:
        raise ErrorValidacion(errores)
    limpio["origen"] = limpio["origen"] or "Desconocido"
    for k in ("telefono", "utm_source", "utm_medium", "utm_campaign"):
        limpio[k] = limpio[k][:120] or None
    return limpio


def responsable_predeterminado(con: sqlite3.Connection) -> int | None:
    fila = con.execute("SELECT id FROM usuarios WHERE activo = 1 ORDER BY id LIMIT 1").fetchone()
    return fila["id"] if fila else None


def crear_solicitud(con: sqlite3.Connection, reloj: Reloj, datos: dict, clave_envio: str) -> tuple[int, bool]:
    """Registra la solicitud y su confirmación en UNA transacción.

    Devuelve (id, creada). Con una clave de envío ya usada (doble clic, recarga)
    devuelve la solicitud existente y creada=False: no hay duplicado ni segundo correo.
    """
    limpio = validar_solicitud(datos)
    if not clave_envio or len(clave_envio) > 64:
        raise ErrorValidacion({"clave_envio": "Recarga el formulario e inténtalo de nuevo."})
    ahora = reloj.ahora()
    with transaccion(con):
        previa = con.execute("SELECT id FROM solicitudes WHERE clave_envio = ?", (clave_envio,)).fetchone()
        if previa:
            return previa["id"], False
        cur = con.execute(
            """INSERT INTO solicitudes (clave_envio, nombre, email, telefono, descripcion, origen,
                   utm_source, utm_medium, utm_campaign, responsable_id, creada_en, vence_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                clave_envio,
                limpio["nombre"],
                limpio["email"],
                limpio["telefono"],
                limpio["descripcion"],
                limpio["origen"],
                limpio["utm_source"],
                limpio["utm_medium"],
                limpio["utm_campaign"],
                responsable_predeterminado(con),
                iso(ahora),
                iso(ahora + timedelta(hours=ajustes.horas_primer_seguimiento)),
            ),
        )
        sid = cur.lastrowid
        con.execute(
            "INSERT INTO trabajos (solicitud_id, tipo, clave, proxima_ejecucion) VALUES (?, 'confirmacion', ?, ?)",
            (sid, f"{sid}:confirmacion", iso(ahora)),
        )
    return sid, True


def registrar_actuacion(
    con: sqlite3.Connection,
    reloj: Reloj,
    solicitud_id: int,
    usuario_id: int,
    tipo: str,
    nota: str = "",
    proxima_accion: datetime | None = None,
    nuevo_estado: str | None = None,
) -> None:
    """Registra una actuación y aplica sus efectos sobre el estado y el vencimiento.

    - Una nota interna no cambia nada más (escenario 5).
    - Un contacto efectivo exige la próxima fecha de seguimiento o cerrar la
      oportunidad, y reemplaza el vencimiento anterior (escenario 6).
    - Cerrar cancela los recordatorios pendientes (escenario 7).
    """
    if tipo not in TIPOS_ACTUACION:
        raise ErrorValidacion({"tipo": "Tipo de actuación desconocido."})
    efectiva = TIPOS_ACTUACION[tipo]
    ahora = reloj.ahora()
    with transaccion(con):
        s = con.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if s is None:
            raise ErrorValidacion({"solicitud": "La solicitud no existe."})
        if s["estado"] in FINALES:
            raise ErrorValidacion({"estado": "La oportunidad ya está cerrada."})
        estado = s["estado"]
        if efectiva and estado == "nueva" and nuevo_estado is None:
            nuevo_estado = "contactada"
        if nuevo_estado and nuevo_estado != estado:
            if nuevo_estado not in TRANSICIONES[estado]:
                raise ErrorValidacion({"estado": f"No se puede pasar de {estado} a {nuevo_estado}."})
            estado = nuevo_estado
        cierra = estado in FINALES
        if efectiva and not cierra:
            if proxima_accion is None:
                raise ErrorValidacion(
                    {"proxima_accion": "Indica la próxima fecha de seguimiento o cierra la oportunidad."}
                )
            if proxima_accion <= ahora:
                raise ErrorValidacion({"proxima_accion": "La próxima fecha de seguimiento debe ser futura."})
        con.execute(
            "INSERT INTO actuaciones (solicitud_id, usuario_id, tipo, nota, efectiva, fecha) VALUES (?, ?, ?, ?, ?, ?)",
            (solicitud_id, usuario_id, tipo, nota.strip()[:4000], int(efectiva), iso(ahora)),
        )
        vence = s["vence_en"]
        if cierra:
            vence = None
        elif efectiva:
            vence = iso(proxima_accion)
        con.execute(
            "UPDATE solicitudes SET estado = ?, vence_en = ?, cerrada_en = ? WHERE id = ?",
            (estado, vence, iso(ahora) if cierra else None, solicitud_id),
        )
        if cierra:
            con.execute(
                "UPDATE trabajos SET estado = 'cancelado' WHERE solicitud_id = ? AND tipo = 'recordatorio' AND estado = 'pendiente'",
                (solicitud_id,),
            )


def reasignar(con: sqlite3.Connection, solicitud_id: int, usuario_id: int) -> None:
    with transaccion(con):
        if not con.execute("SELECT 1 FROM usuarios WHERE id = ? AND activo = 1", (usuario_id,)).fetchone():
            raise ErrorValidacion({"responsable": "Usuario no válido."})
        con.execute("UPDATE solicitudes SET responsable_id = ? WHERE id = ?", (usuario_id, solicitud_id))
