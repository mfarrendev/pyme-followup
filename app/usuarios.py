import hashlib
import hmac
import secrets
import sqlite3

# scrypt con los parámetros que recomienda OWASP (N=2^17, r=8, p=1).
N, R, P = 2**17, 8, 1


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=N, r=R, p=P, maxmem=256 * 1024 * 1024)
    return f"scrypt${sal.hex()}${h.hex()}"


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        _, sal, h = guardado.split("$")
    except ValueError:
        return False
    calculado = hashlib.scrypt(
        clave.encode(), salt=bytes.fromhex(sal), n=N, r=R, p=P, maxmem=256 * 1024 * 1024
    )
    return hmac.compare_digest(calculado.hex(), h)


# Hash de una clave que nadie tiene: cuando el email no existe se verifica
# contra esto, para que la respuesta tarde lo mismo y no delate qué emails hay.
_HASH_SEÑUELO = hash_clave(secrets.token_hex(16))


def crear_usuario(con: sqlite3.Connection, nombre: str, email: str, clave: str) -> int:
    if len(clave) < 12:
        raise ValueError("La clave debe tener al menos 12 caracteres")
    cur = con.execute(
        "INSERT INTO usuarios (nombre, email, hash_clave) VALUES (?, ?, ?)",
        (nombre, email.strip().lower(), hash_clave(clave)),
    )
    return cur.lastrowid


def autenticar(con: sqlite3.Connection, email: str, clave: str) -> sqlite3.Row | None:
    u = con.execute(
        "SELECT * FROM usuarios WHERE email = ? AND activo = 1", (email.strip().lower(),)
    ).fetchone()
    if u is None:
        verificar_clave(clave, _HASH_SEÑUELO)
        return None
    return u if verificar_clave(clave, u["hash_clave"]) else None
