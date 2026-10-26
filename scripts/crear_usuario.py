"""Crea un usuario del panel. Uso: python -m scripts.crear_usuario "Nombre" email@empresa.cl"""

import getpass
import sys

from app.config import ajustes
from app.db import conectar, inicializar
from app.usuarios import crear_usuario

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    inicializar(ajustes.db_path)
    clave = getpass.getpass("Clave (mínimo 12 caracteres): ")
    con = conectar(ajustes.db_path)
    print(f"Usuario {crear_usuario(con, sys.argv[1], sys.argv[2], clave)} creado.")
