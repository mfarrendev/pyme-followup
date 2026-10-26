import sqlite3
from contextlib import contextmanager
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    hash_clave TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY,
    clave_envio TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL,
    telefono TEXT,
    descripcion TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'Desconocido',
    utm_source TEXT, utm_medium TEXT, utm_campaign TEXT,
    estado TEXT NOT NULL DEFAULT 'nueva'
        CHECK (estado IN ('nueva', 'contactada', 'presupuesto_enviado', 'ganada', 'perdida')),
    responsable_id INTEGER REFERENCES usuarios(id),
    creada_en TEXT NOT NULL,
    vence_en TEXT,
    cerrada_en TEXT
);
CREATE TABLE IF NOT EXISTS actuaciones (
    id INTEGER PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    tipo TEXT NOT NULL,
    nota TEXT NOT NULL DEFAULT '',
    efectiva INTEGER NOT NULL,
    fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trabajos (
    id INTEGER PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('confirmacion', 'recordatorio', 'aviso_fallo')),
    vencimiento TEXT,
    clave TEXT NOT NULL UNIQUE,
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'en_proceso', 'enviado', 'fallido', 'cancelado')),
    intentos INTEGER NOT NULL DEFAULT 0,
    proxima_ejecucion TEXT NOT NULL,
    bloqueado_hasta TEXT,
    ultimo_error TEXT,
    enviado_en TEXT,
    id_proveedor TEXT
);
-- Correos capturados en modo "memoria": la demo nunca escribe a una dirección real.
CREATE TABLE IF NOT EXISTS correos_capturados (
    id INTEGER PRIMARY KEY,
    para TEXT NOT NULL,
    asunto TEXT NOT NULL,
    cuerpo TEXT NOT NULL,
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_solicitudes_vence ON solicitudes(estado, vence_en);
CREATE INDEX IF NOT EXISTS idx_trabajos_pendientes ON trabajos(estado, proxima_ejecucion);
"""


def conectar(ruta: Path) -> sqlite3.Connection:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI abre la conexión de una petición en un hilo
    # y puede usarla en otro. Es seguro porque cada petición tiene la suya.
    con = sqlite3.connect(ruta, isolation_level=None, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def inicializar(ruta: Path) -> None:
    con = conectar(ruta)
    try:
        con.executescript(ESQUEMA)
    finally:
        con.close()


@contextmanager
def transaccion(con: sqlite3.Connection):
    """BEGIN IMMEDIATE: toma el bloqueo de escritura al empezar, no a mitad.

    Así el trabajador y el panel no se pisan, y una solicitud queda guardada
    junto con su trabajo de confirmación o no queda ninguno de los dos.
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")
