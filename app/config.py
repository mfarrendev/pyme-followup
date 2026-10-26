from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE = Path(__file__).parent.parent


class Ajustes(BaseSettings):
    """Configuración por variables de entorno con prefijo PYME_ (ver .env.example)."""

    db_path: Path = BASE / "datos" / "pyme.db"
    # Firma la cookie de sesión. Sin valor propio, el panel no arranca en producción.
    clave_secreta: str = "solo-para-desarrollo"
    produccion: bool = False
    zona_horaria: str = "America/Santiago"
    nombre_empresa: str = "Remodelaciones Demo"
    # Plazo del primer seguimiento: regla provisional del caso de estudio (ESPECIFICACION.md).
    horas_primer_seguimiento: int = 48
    # Correo: "memoria" captura los envíos en la base (demo y pruebas); "smtp" envía de verdad.
    correo_modo: str = "memoria"
    smtp_host: str = "localhost"
    smtp_puerto: int = 1025
    smtp_usuario: str = ""
    smtp_clave: str = ""
    smtp_tls: bool = False
    correo_remitente: str = "no-responder@example.com"
    # Límite del formulario público por IP.
    envios_por_minuto: int = 5

    model_config = SettingsConfigDict(env_prefix="PYME_", env_file=".env", extra="ignore")


ajustes = Ajustes()
