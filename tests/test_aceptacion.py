"""Los once escenarios de aceptación de docs/ESPECIFICACION.md, uno por prueba.

Cada prueba se midió poniendo a mano el defecto que vigila: la tabla está en
docs/EVALUACION.md, § Pruebas del MVP.
"""

from datetime import timedelta

from app import servicio
from app.correo import ErrorPermanente, ErrorTransitorio
from app.trabajador import MAX_INTENTOS, crear_recordatorios, ejecutar
from tests.conftest import DATOS


class EnviadorPrueba:
    def __init__(self, falla=None):
        self.enviados, self.falla = [], falla

    def enviar(self, para, asunto, cuerpo):
        if self.falla:
            raise self.falla
        self.enviados.append((para, asunto))
        return "id"


def trabajos(con, tipo=None):
    sql = "SELECT * FROM trabajos" + (" WHERE tipo = ?" if tipo else "")
    return con.execute(sql, (tipo,) if tipo else ()).fetchall()


def crear(con, reloj, clave="k1", **extra):
    return servicio.crear_solicitud(con, reloj, {**DATOS, **extra}, clave)[0]


# 1
def test_solicitud_valida_aparece_una_vez_y_genera_confirmacion(cliente, con):
    r = cliente.post("/solicitar", data={**DATOS, "clave_envio": "abc"}, follow_redirects=False)
    assert r.status_code == 303
    assert con.execute("SELECT count(*) FROM solicitudes").fetchone()[0] == 1
    assert [t["tipo"] for t in trabajos(con)] == ["confirmacion"]


# 2
def test_email_invalido_muestra_error_y_no_genera_nada(cliente, con):
    r = cliente.post("/solicitar", data={**DATOS, "email": "no-es-un-email", "clave_envio": "abc"})
    assert r.status_code == 422 and "El email no es válido" in r.text
    assert con.execute("SELECT count(*) FROM solicitudes").fetchone()[0] == 0
    assert trabajos(con) == []


# 3
def test_mismo_envio_con_la_misma_clave_no_duplica(cliente, con):
    for _ in range(2):
        cliente.post("/solicitar", data={**DATOS, "clave_envio": "doble-clic"}, follow_redirects=False)
    assert con.execute("SELECT count(*) FROM solicitudes").fetchone()[0] == 1
    assert len(trabajos(con, "confirmacion")) == 1


# 4
def test_sin_contacto_efectivo_hay_recordatorio_al_vencer(con, reloj, usuario_id):
    crear(con, reloj)
    reloj.avanzar(hours=47, minutes=59)
    ejecutar(con, reloj, EnviadorPrueba())
    assert trabajos(con, "recordatorio") == []
    reloj.avanzar(minutes=1)
    env = EnviadorPrueba()
    ejecutar(con, reloj, env)
    assert [t["estado"] for t in trabajos(con, "recordatorio")] == ["enviado"]
    assert env.enviados == [("ana@example.com", "Seguimiento pendiente: solicitud 1")]


# 5
def test_una_nota_interna_no_evita_el_recordatorio(con, reloj, usuario_id):
    sid = crear(con, reloj)
    reloj.avanzar(hours=1)
    servicio.registrar_actuacion(con, reloj, sid, usuario_id, "nota", "lo llamo mañana")
    reloj.avanzar(hours=48)
    ejecutar(con, reloj, EnviadorPrueba())
    assert len(trabajos(con, "recordatorio")) == 1


# 6
def test_contacto_con_proxima_accion_reemplaza_el_vencimiento(con, reloj, usuario_id):
    sid = crear(con, reloj)
    reloj.avanzar(hours=2)
    servicio.registrar_actuacion(
        con, reloj, sid, usuario_id, "llamada", proxima_accion=reloj.ahora() + timedelta(days=5)
    )
    reloj.avanzar(hours=48)  # pasó el vencimiento original
    ejecutar(con, reloj, EnviadorPrueba())
    assert trabajos(con, "recordatorio") == []
    assert con.execute("SELECT estado FROM solicitudes").fetchone()[0] == "contactada"
    reloj.avanzar(days=4)  # llega el nuevo vencimiento
    ejecutar(con, reloj, EnviadorPrueba())
    assert len(trabajos(con, "recordatorio")) == 1


def test_contacto_sin_proxima_accion_ni_cierre_se_rechaza(con, reloj, usuario_id):
    sid = crear(con, reloj)
    try:
        servicio.registrar_actuacion(con, reloj, sid, usuario_id, "llamada")
    except servicio.ErrorValidacion as e:
        assert "proxima_accion" in e.errores
    else:
        raise AssertionError("debió rechazarse")


# 7
def test_cerrar_cancela_los_recordatorios_pendientes(con, reloj, usuario_id):
    sid = crear(con, reloj)
    reloj.avanzar(hours=49)
    crear_recordatorios(con, reloj)  # queda pendiente, sin enviar
    servicio.registrar_actuacion(con, reloj, sid, usuario_id, "llamada", nuevo_estado="perdida")
    assert [t["estado"] for t in trabajos(con, "recordatorio")] == ["cancelado"]
    reloj.avanzar(days=10)
    ejecutar(con, reloj, EnviadorPrueba())
    assert len(trabajos(con, "recordatorio")) == 1


# 8
def test_correr_el_proceso_dos_veces_no_duplica(con, reloj, usuario_id):
    crear(con, reloj)
    reloj.avanzar(hours=48)
    ejecutar(con, reloj, EnviadorPrueba())
    ejecutar(con, reloj, EnviadorPrueba())
    reloj.avanzar(minutes=5)
    ejecutar(con, reloj, EnviadorPrueba())
    assert len(trabajos(con, "recordatorio")) == 1


# 9
def test_fallo_de_correo_respeta_el_limite_y_queda_visible(con, reloj, usuario_id, sesion):
    crear(con, reloj)
    caido = EnviadorPrueba(falla=ErrorTransitorio("SMTPConnectError"))
    ejecutar(con, reloj, caido)  # intento 1
    reloj.avanzar(minutes=1)
    ejecutar(con, reloj, caido)  # intento 2
    reloj.avanzar(minutes=5)
    ejecutar(con, reloj, caido)  # intento 3: se agota
    reloj.avanzar(minutes=30)
    ejecutar(con, reloj, caido)
    (conf,) = trabajos(con, "confirmacion")
    assert conf["estado"] == "fallido" and conf["intentos"] == MAX_INTENTOS
    assert len(trabajos(con, "aviso_fallo")) == 1  # se informa al responsable
    assert "correo con error" in sesion.get("/panel").text


def test_error_permanente_no_se_reintenta(con, reloj, usuario_id):
    crear(con, reloj)
    ejecutar(con, reloj, EnviadorPrueba(falla=ErrorPermanente("SMTPAuthenticationError")))
    (conf,) = trabajos(con, "confirmacion")
    assert conf["estado"] == "fallido" and conf["intentos"] == 1


# 10
def test_sin_sesion_no_se_consulta_ni_se_exporta(cliente, con, reloj):
    crear(con, reloj)
    for ruta in ("/panel", "/solicitudes/1", "/exportar.csv"):
        r = cliente.get(ruta, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", ruta
        assert "cliente@example.com" not in r.text


# 11
def test_cambio_de_estado_con_recordatorio_pendiente_evita_aviso_obsoleto(con, reloj, usuario_id):
    sid = crear(con, reloj)
    reloj.avanzar(hours=49)
    crear_recordatorios(con, reloj)
    # Mientras el recordatorio espera en la cola, alguien registra el contacto
    # y mueve la fecha. La cancelación de cierre no aplica: no se cerró.
    servicio.registrar_actuacion(
        con, reloj, sid, usuario_id, "llamada", proxima_accion=reloj.ahora() + timedelta(days=3)
    )
    env = EnviadorPrueba()
    ejecutar(con, reloj, env)
    assert [t["estado"] for t in trabajos(con, "recordatorio")] == ["cancelado"]
    assert all("Seguimiento" not in asunto for _, asunto in env.enviados)
