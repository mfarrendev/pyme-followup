"""Datos de demostración: un usuario y las solicitudes de examples/solicitudes.csv,
repartidas en los últimos días, con algunas actuaciones. Los correos se capturan
en la base; nada sale a direcciones reales.

Uso: python -m scripts.cargar_demo
"""

import csv
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app import servicio
from app.config import ajustes
from app.correo import EnviadorMemoria
from app.db import conectar, inicializar
from app.reloj import RelojFijo
from app.trabajador import ejecutar
from app.usuarios import crear_usuario

if __name__ == "__main__":
    inicializar(ajustes.db_path)
    con = conectar(ajustes.db_path)
    if con.execute("SELECT count(*) FROM usuarios").fetchone()[0]:
        raise SystemExit(f"{ajustes.db_path} ya tiene datos: corre `make clean` para cargar la demo de nuevo.")
    clave = secrets.token_urlsafe(12)
    uid = crear_usuario(con, "Ana Comercial", "ana@example.com", clave)

    ahora = datetime.now(UTC).replace(microsecond=0)
    reloj = RelojFijo(ahora - timedelta(days=4))
    ruta = Path(__file__).parent.parent / "examples" / "solicitudes.csv"
    ids = []
    for fila in csv.DictReader(ruta.open(encoding="utf-8")):
        reloj.avanzar(hours=15)
        ids.append(servicio.crear_solicitud(con, reloj, fila, f"demo-{fila['id']}")[0])
        ejecutar(con, reloj, EnviadorMemoria(con, reloj))

    # Una contactada a tiempo, una ganada, una con solo una nota (sigue vencida).
    servicio.registrar_actuacion(
        con, reloj, ids[0], uid, "llamada", "Quiere visita técnica", proxima_accion=ahora + timedelta(days=2)
    )
    servicio.registrar_actuacion(
        con,
        reloj,
        ids[1],
        uid,
        "presupuesto",
        "Presupuesto enviado",
        proxima_accion=ahora + timedelta(days=5),
        nuevo_estado="contactada",
    )
    servicio.registrar_actuacion(con, reloj, ids[3], uid, "nota", "No contesta el teléfono")
    reloj.momento = ahora
    ejecutar(con, reloj, EnviadorMemoria(con, reloj))

    print(f"Demo cargada en {ajustes.db_path}")
    print(f"Panel: ana@example.com / {clave}")
