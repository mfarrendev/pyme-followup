import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import servicio
from app.config import ajustes
from app.db import conectar, inicializar
from app.exportar import generar_csv
from app.reloj import Reloj, desde_iso, iso
from app.usuarios import autenticar

ZONA = ZoneInfo(ajustes.zona_horaria)
plantillas = Jinja2Templates(directory=Path(__file__).parent / "templates")


def a_local(texto: str | None) -> str:
    if not texto:
        return "—"
    return desde_iso(texto).astimezone(ZONA).strftime("%d-%m-%Y %H:%M")


plantillas.env.filters["local"] = a_local
plantillas.env.filters["etiqueta"] = lambda clave: {
    "confirmacion": "confirmación",
    "aviso_fallo": "aviso de fallo",
    "reunion": "reunión",
    "presupuesto_enviado": "presupuesto enviado",
    "en_proceso": "en proceso",
}.get(clave, clave)


class NoAutenticado(Exception):
    pass


class LimiteEnvios:
    """Ventana deslizante por IP para el formulario público (spam).

    En memoria: alcanza para un proceso; con varios procesos haría falta una
    tabla o Redis.
    """

    def __init__(self, por_minuto: int):
        self.por_minuto = por_minuto
        self.marcas: dict[str, deque] = defaultdict(deque)

    def permitir(self, ip: str) -> bool:
        ahora = time.monotonic()
        marcas = self.marcas[ip]
        while marcas and ahora - marcas[0] > 60:
            marcas.popleft()
        if len(marcas) >= self.por_minuto:
            return False
        marcas.append(ahora)
        return True


def crear_app(db_path: Path | None = None, reloj: Reloj | None = None) -> FastAPI:
    if ajustes.produccion and ajustes.clave_secreta == "solo-para-desarrollo":
        raise RuntimeError("Define PYME_CLAVE_SECRETA antes de correr en producción.")
    ruta = db_path or ajustes.db_path
    inicializar(ruta)
    app = FastAPI(title="Pyme FollowUp", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=ajustes.clave_secreta,
        session_cookie="pyme_sesion",
        same_site="lax",
        https_only=ajustes.produccion,
        max_age=8 * 3600,
    )
    app.state.reloj = reloj or Reloj()
    app.state.limite = LimiteEnvios(ajustes.envios_por_minuto)

    @app.middleware("http")
    async def cabeceras_seguridad(request: Request, call_next):
        r = await call_next(request)
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "same-origin"
        r.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        return r

    @app.exception_handler(NoAutenticado)
    async def a_login(request: Request, exc: NoAutenticado):
        return RedirectResponse("/login", status_code=303)

    def con():
        c = conectar(ruta)
        try:
            yield c
        finally:
            c.close()

    def usuario(request: Request, c: sqlite3.Connection = Depends(con)) -> sqlite3.Row:
        uid = request.session.get("usuario_id")
        u = (
            c.execute("SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,)).fetchone()
            if uid
            else None
        )
        if u is None:
            raise NoAutenticado()
        return u

    def token_csrf(request: Request) -> str:
        if "csrf" not in request.session:
            request.session["csrf"] = secrets.token_urlsafe(32)
        return request.session["csrf"]

    def exigir_csrf(request: Request, csrf: str = Form("")) -> None:
        esperado = request.session.get("csrf", "")
        if not esperado or not secrets.compare_digest(esperado, csrf):
            raise HTTPException(403, "Formulario vencido: recarga la página.")

    def render(request: Request, plantilla: str, status: int = 200, **ctx) -> HTMLResponse:
        ctx.update(empresa=ajustes.nombre_empresa, csrf=token_csrf(request))
        return plantillas.TemplateResponse(request, plantilla, ctx, status_code=status)

    # ── Público ────────────────────────────────────────────────────────────

    @app.get("/")
    def inicio():
        return RedirectResponse("/solicitar", status_code=303)

    @app.get("/solicitar", response_class=HTMLResponse)
    def formulario(request: Request):
        utm = {k: request.query_params.get(k, "")[:120] for k in ("utm_source", "utm_medium", "utm_campaign")}
        return render(request, "solicitar.html", datos=utm, errores={}, clave_envio=secrets.token_urlsafe(16))

    @app.post("/solicitar", response_class=HTMLResponse)
    async def enviar_solicitud(request: Request, c: sqlite3.Connection = Depends(con)):
        datos = dict(await request.form())
        ip = request.client.host if request.client else "?"
        if not app.state.limite.permitir(ip):
            return render(
                request,
                "solicitar.html",
                429,
                datos=datos,
                clave_envio=datos.get("clave_envio", ""),
                errores={"general": "Demasiados envíos seguidos. Espera un minuto."},
            )
        try:
            servicio.crear_solicitud(c, app.state.reloj, datos, str(datos.get("clave_envio", "")))
        except servicio.ErrorValidacion as e:
            return render(
                request,
                "solicitar.html",
                422,
                datos=datos,
                errores=e.errores,
                clave_envio=datos.get("clave_envio", ""),
            )
        return RedirectResponse("/gracias", status_code=303)

    @app.get("/gracias", response_class=HTMLResponse)
    def gracias(request: Request):
        return render(request, "gracias.html")

    # ── Sesión ─────────────────────────────────────────────────────────────

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return render(request, "login.html", error=None)

    @app.post("/login", response_class=HTMLResponse, dependencies=[Depends(exigir_csrf)])
    def login(
        request: Request, email: str = Form(...), clave: str = Form(...), c: sqlite3.Connection = Depends(con)
    ):
        u = autenticar(c, email, clave)
        if u is None:
            return render(request, "login.html", 401, error="Email o clave incorrectos.")
        request.session.clear()  # sesión nueva al entrar
        request.session["usuario_id"] = u["id"]
        return RedirectResponse("/panel", status_code=303)

    @app.post("/logout", dependencies=[Depends(exigir_csrf)])
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # ── Panel privado ──────────────────────────────────────────────────────

    @app.get("/panel", response_class=HTMLResponse)
    def panel(
        request: Request,
        estado: str = "",
        responsable: str = "",
        origen: str = "",
        vencidas: str = "",
        q: str = "",
        u: sqlite3.Row = Depends(usuario),
        c: sqlite3.Connection = Depends(con),
    ):
        ahora = iso(app.state.reloj.ahora())
        where, params = ["1=1"], []
        if estado in servicio.ESTADOS:
            where.append("s.estado = ?")
            params.append(estado)
        if responsable.isdigit():
            where.append("s.responsable_id = ?")
            params.append(int(responsable))
        if origen:
            where.append("s.origen = ?")
            params.append(origen)
        if vencidas:
            where.append(
                "s.vence_en IS NOT NULL AND s.vence_en <= ? AND s.estado NOT IN ('ganada', 'perdida')"
            )
            params.append(ahora)
        if q:
            where.append("(s.nombre LIKE ? OR s.email LIKE ? OR s.descripcion LIKE ?)")
            params += [f"%{q}%"] * 3
        solicitudes = c.execute(
            f"""SELECT s.*, us.nombre AS responsable,
                       (SELECT count(*) FROM trabajos t WHERE t.solicitud_id = s.id AND t.estado = 'fallido') AS fallidos
                FROM solicitudes s LEFT JOIN usuarios us ON us.id = s.responsable_id
                WHERE {" AND ".join(where)} ORDER BY s.vence_en IS NULL, s.vence_en, s.id DESC""",
            params,
        ).fetchall()
        return render(
            request,
            "panel.html",
            u=u,
            solicitudes=solicitudes,
            ahora=ahora,
            filtros={
                "estado": estado,
                "responsable": responsable,
                "origen": origen,
                "vencidas": vencidas,
                "q": q,
            },
            estados=servicio.ESTADOS,
            usuarios=c.execute("SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre").fetchall(),
            origenes=[r[0] for r in c.execute("SELECT DISTINCT origen FROM solicitudes ORDER BY 1")],
            indicadores=indicadores(c, ahora),
        )

    @app.get("/solicitudes/{sid}", response_class=HTMLResponse)
    def ficha(
        request: Request, sid: int, u: sqlite3.Row = Depends(usuario), c: sqlite3.Connection = Depends(con)
    ):
        s = c.execute(
            "SELECT s.*, us.nombre AS responsable FROM solicitudes s LEFT JOIN usuarios us ON us.id = s.responsable_id WHERE s.id = ?",
            (sid,),
        ).fetchone()
        if s is None:
            raise HTTPException(404)
        return render(
            request,
            "ficha.html",
            u=u,
            s=s,
            error=request.query_params.get("error"),
            actuaciones=c.execute(
                "SELECT a.*, us.nombre FROM actuaciones a JOIN usuarios us ON us.id = a.usuario_id WHERE solicitud_id = ? ORDER BY fecha DESC",
                (sid,),
            ).fetchall(),
            trabajos=c.execute(
                "SELECT * FROM trabajos WHERE solicitud_id = ? ORDER BY id", (sid,)
            ).fetchall(),
            usuarios=c.execute("SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre").fetchall(),
            transiciones=sorted(servicio.TRANSICIONES[s["estado"]]),
            tipos=list(servicio.TIPOS_ACTUACION),
        )

    @app.post("/solicitudes/{sid}/actuacion", dependencies=[Depends(exigir_csrf)])
    def actuacion(
        sid: int,
        tipo: str = Form(...),
        nota: str = Form(""),
        proxima_accion: str = Form(""),
        nuevo_estado: str = Form(""),
        u: sqlite3.Row = Depends(usuario),
        c: sqlite3.Connection = Depends(con),
    ):
        proxima = None
        if proxima_accion:
            # El input datetime-local llega en la hora de la empresa, sin zona.
            proxima = datetime.fromisoformat(proxima_accion).replace(tzinfo=ZONA)
        try:
            servicio.registrar_actuacion(
                c, app.state.reloj, sid, u["id"], tipo, nota, proxima, nuevo_estado or None
            )
        except servicio.ErrorValidacion as e:
            return RedirectResponse(
                f"/solicitudes/{sid}?error={quote(next(iter(e.errores.values())))}", status_code=303
            )
        return RedirectResponse(f"/solicitudes/{sid}", status_code=303)

    @app.post("/solicitudes/{sid}/responsable", dependencies=[Depends(exigir_csrf)])
    def responsable_(
        sid: int,
        responsable: int = Form(...),
        u: sqlite3.Row = Depends(usuario),
        c: sqlite3.Connection = Depends(con),
    ):
        try:
            servicio.reasignar(c, sid, responsable)
        except servicio.ErrorValidacion as e:
            return RedirectResponse(
                f"/solicitudes/{sid}?error={quote(next(iter(e.errores.values())))}", status_code=303
            )
        return RedirectResponse(f"/solicitudes/{sid}", status_code=303)

    @app.get("/exportar.csv")
    def exportar(u: sqlite3.Row = Depends(usuario), c: sqlite3.Connection = Depends(con)):
        return Response(
            generar_csv(c, ajustes.horas_primer_seguimiento),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="solicitudes.csv"'},
        )

    return app


def indicadores(c: sqlite3.Connection, ahora: str) -> dict:
    """Cobertura del seguimiento según EVALUACION.md: de las solicitudes cuyo primer
    plazo ya venció, cuántas tuvieron una actuación efectiva dentro de ese plazo."""
    horas = ajustes.horas_primer_seguimiento
    fila = c.execute(
        f"""SELECT
              count(*) AS total,
              sum(estado NOT IN ('ganada', 'perdida') AND vence_en IS NOT NULL AND vence_en <= :ahora) AS vencidas,
              sum(datetime(creada_en, '+{horas} hours') <= datetime(:ahora)) AS plazo_cumplido_o_vencido,
              sum(datetime(creada_en, '+{horas} hours') <= datetime(:ahora) AND EXISTS (
                  SELECT 1 FROM actuaciones a WHERE a.solicitud_id = s.id AND a.efectiva = 1
                  AND datetime(a.fecha) <= datetime(s.creada_en, '+{horas} hours'))) AS atendidas_en_plazo
            FROM solicitudes s""",
        {"ahora": ahora},
    ).fetchone()
    base = fila["plazo_cumplido_o_vencido"] or 0
    return {
        "total": fila["total"],
        "vencidas": fila["vencidas"] or 0,
        "cobertura": None if base == 0 else round(100 * (fila["atendidas_en_plazo"] or 0) / base),
        "base_cobertura": base,
    }
