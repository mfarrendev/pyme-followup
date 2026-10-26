import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db import conectar, inicializar
from app.reloj import RelojFijo
from app.usuarios import crear_usuario
from app.web import crear_app

CLAVE = "clave-de-prueba-larga"


@pytest.fixture
def reloj():
    return RelojFijo(datetime(2026, 3, 2, 12, 0, tzinfo=UTC))


@pytest.fixture
def ruta(tmp_path):
    r = tmp_path / "pyme.db"
    inicializar(r)
    return r


@pytest.fixture
def con(ruta):
    c = conectar(ruta)
    yield c
    c.close()


@pytest.fixture
def usuario_id(con):
    return crear_usuario(con, "Ana Comercial", "ana@example.com", CLAVE)


@pytest.fixture
def cliente(ruta, reloj, usuario_id):
    return TestClient(crear_app(ruta, reloj))


def csrf_de(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


@pytest.fixture
def sesion(cliente):
    """Cliente con sesión iniciada."""
    token = csrf_de(cliente.get("/login").text)
    r = cliente.post(
        "/login", data={"email": "ana@example.com", "clave": CLAVE, "csrf": token}, follow_redirects=False
    )
    assert r.status_code == 303
    return cliente


DATOS = {"nombre": "Cliente Ficticio", "email": "cliente@example.com", "descripcion": "Remodelar la cocina"}
