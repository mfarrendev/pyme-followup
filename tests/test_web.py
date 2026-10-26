"""Seguridad y detalles de la interfaz que no son escenarios de aceptación."""

import re

from app.exportar import neutralizar
from tests.conftest import DATOS, csrf_de


def test_post_privado_sin_csrf_se_rechaza(sesion, con, reloj):
    sesion.post("/solicitar", data={**DATOS, "clave_envio": "a"})
    r = sesion.post("/solicitudes/1/actuacion", data={"tipo": "nota", "nota": "x"})
    assert r.status_code == 403
    assert con.execute("SELECT count(*) FROM actuaciones").fetchone()[0] == 0


def test_login_con_clave_incorrecta(cliente):
    token = csrf_de(cliente.get("/login").text)
    r = cliente.post(
        "/login", data={"email": "ana@example.com", "clave": "otra-clave-cualquiera", "csrf": token}
    )
    assert r.status_code == 401
    assert cliente.get("/panel", follow_redirects=False).status_code == 303


def test_actuacion_desde_el_panel(sesion, con):
    sesion.post("/solicitar", data={**DATOS, "clave_envio": "a"})
    token = csrf_de(sesion.get("/solicitudes/1").text)
    r = sesion.post(
        "/solicitudes/1/actuacion",
        data={"tipo": "llamada", "nota": "le interesa", "proxima_accion": "2026-03-10T10:00", "csrf": token},
        follow_redirects=False,
    )
    assert r.status_code == 303
    s = con.execute("SELECT estado, vence_en FROM solicitudes").fetchone()
    # 10:00 en Santiago (UTC-3 en marzo) son las 13:00 UTC.
    assert tuple(s) == ("contactada", "2026-03-10T13:00:00+00:00")


def test_html_del_cliente_se_escapa(sesion):
    sesion.post("/solicitar", data={**DATOS, "nombre": "<script>alert(1)</script>", "clave_envio": "a"})
    html = sesion.get("/panel").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_csv_neutraliza_formulas(sesion):
    sesion.post("/solicitar", data={**DATOS, "nombre": '=HYPERLINK("http://x")', "clave_envio": "a"})
    csv = sesion.get("/exportar.csv").text
    assert "'=HYPERLINK" in csv
    assert neutralizar("-1") == "'-1" and neutralizar("Ana") == "Ana"


def test_limite_de_envios_del_formulario(cliente):
    codigos = [
        cliente.post("/solicitar", data={**DATOS, "clave_envio": f"k{i}"}).status_code for i in range(7)
    ]
    assert codigos.count(429) == 2


def test_utm_de_la_campana_se_conserva(cliente, con):
    html = cliente.get("/solicitar?utm_source=google&utm_campaign=cocinas").text
    clave = re.search(r'name="clave_envio" value="([^"]+)"', html).group(1)
    cliente.post(
        "/solicitar", data={**DATOS, "clave_envio": clave, "utm_source": "google", "utm_campaign": "cocinas"}
    )
    assert tuple(con.execute("SELECT utm_source, utm_campaign, origen FROM solicitudes").fetchone()) == (
        "google",
        "cocinas",
        "Desconocido",
    )
