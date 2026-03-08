import os
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import routes as api_routes
from app.api.routes import router as api_router


class NoCacheStaticFiles(StaticFiles):
    def file_response(self, full_path, stat_result, scope, status_code=200):  # type: ignore[override]
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


def _resolve_asset_version(frontend_dir: Path, app_version: str) -> str:
    override = os.getenv("APP_ASSET_VERSION", "").strip()
    if override and override.lower() != "dev":
        return override

    digest = sha256()
    for path in sorted(frontend_dir.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(frontend_dir).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12] or app_version


def create_app() -> FastAPI:
    app = FastAPI(title="Poker Bots Playground", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    repo_root = Path(__file__).resolve().parents[2]
    frontend_dir = repo_root / "frontend"
    if frontend_dir.exists():
        asset_version = _resolve_asset_version(frontend_dir, app.version)
        app.mount("/static", NoCacheStaticFiles(directory=str(frontend_dir), html=False), name="frontend-static")
        template_files = {
            "login": frontend_dir / "login.html",
            "lobby": frontend_dir / "lobby.html",
            "table-detail": frontend_dir / "table-detail.html",
            "my-bots": frontend_dir / "my-bots.html",
        }
        template_cache = {
            name: path.read_text(encoding="utf-8")
            for name, path in template_files.items()
            if path.exists()
        }

        def render_template(template_name: str) -> HTMLResponse:
            html = template_cache[template_name].replace("__ASSET_VERSION__", asset_version)
            response = HTMLResponse(content=html)
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            return response

        def is_authenticated(request: Request) -> bool:
            session_id = request.cookies.get(api_routes.auth_settings.session_cookie_name)
            return api_routes.auth_service.get_user_from_session(session_id) is not None

        @app.get("/", include_in_schema=False)
        @app.get("/index.html", include_in_schema=False)
        def serve_root(request: Request) -> RedirectResponse:
            target = "/lobby" if is_authenticated(request) else "/login"
            return RedirectResponse(url=target, status_code=302)

        @app.get("/login", include_in_schema=False)
        def serve_login(request: Request) -> Response:
            if is_authenticated(request):
                return RedirectResponse(url="/lobby", status_code=302)
            return render_template("login")

        @app.get("/lobby", include_in_schema=False)
        def serve_lobby(request: Request) -> Response:
            if not is_authenticated(request):
                return RedirectResponse(url="/login", status_code=302)
            return render_template("lobby")

        @app.get("/tables/{table_id}", include_in_schema=False)
        def serve_table_detail(request: Request, table_id: str) -> Response:
            if not is_authenticated(request):
                return RedirectResponse(url="/login", status_code=302)
            return render_template("table-detail")

        @app.get("/my-bots", include_in_schema=False)
        def serve_my_bots(request: Request) -> Response:
            if not is_authenticated(request):
                return RedirectResponse(url="/login", status_code=302)
            return render_template("my-bots")

    return app


app = create_app()
