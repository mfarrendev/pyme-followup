"""Reloj inyectable: las pruebas avanzan el tiempo sin esperar 48 horas reales."""

from datetime import UTC, datetime, timedelta


class Reloj:
    def ahora(self) -> datetime:
        return datetime.now(UTC)


class RelojFijo(Reloj):
    def __init__(self, inicio: datetime):
        self.momento = inicio

    def ahora(self) -> datetime:
        return self.momento

    def avanzar(self, **delta) -> None:
        self.momento += timedelta(**delta)


def iso(momento: datetime) -> str:
    """Fechas en UTC, en texto ISO: se ordenan y comparan bien en SQLite."""
    return momento.astimezone(UTC).isoformat(timespec="seconds")


def desde_iso(texto: str) -> datetime:
    return datetime.fromisoformat(texto)
