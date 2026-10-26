"""Exportación CSV para la evaluación (EVALUACION.md, § Indicadores)."""

import csv
import io
import sqlite3
from datetime import timedelta

from app.reloj import desde_iso, iso

COLUMNAS = [
    "id",
    "creada_en",
    "nombre",
    "email",
    "origen",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "estado",
    "responsable",
    "vence_en",
    "cerrada_en",
    "primera_actuacion_efectiva",
    "primer_seguimiento_en_plazo",
    "actuaciones_efectivas",
]


def neutralizar(valor) -> str:
    """Una celda que empieza con = + - @ se ejecuta como fórmula al abrir el CSV
    en una planilla. Se antepone un apóstrofo para que quede como texto."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def generar_csv(con: sqlite3.Connection, horas_plazo: int) -> str:
    filas = con.execute(
        """SELECT s.*, u.email AS responsable,
                  (SELECT min(fecha) FROM actuaciones a WHERE a.solicitud_id = s.id AND a.efectiva = 1) AS primera,
                  (SELECT count(*) FROM actuaciones a WHERE a.solicitud_id = s.id AND a.efectiva = 1) AS efectivas
           FROM solicitudes s LEFT JOIN usuarios u ON u.id = s.responsable_id ORDER BY s.id"""
    ).fetchall()
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(COLUMNAS)
    for f in filas:
        en_plazo = ""
        if f["primera"]:
            en_plazo = "si" if f["primera"] <= _sumar_horas(f["creada_en"], horas_plazo) else "no"
        w.writerow(
            neutralizar(v)
            for v in (
                f["id"],
                f["creada_en"],
                f["nombre"],
                f["email"],
                f["origen"],
                f["utm_source"],
                f["utm_medium"],
                f["utm_campaign"],
                f["estado"],
                f["responsable"],
                f["vence_en"],
                f["cerrada_en"],
                f["primera"],
                en_plazo,
                f["efectivas"],
            )
        )
    return salida.getvalue()


def _sumar_horas(iso_texto: str, horas: int) -> str:
    return iso(desde_iso(iso_texto) + timedelta(hours=horas))
