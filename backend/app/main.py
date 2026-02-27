import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import routes as api_routes
from app.api.routes import router as api_router


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
        app.mount("/static", StaticFiles(directory=str(frontend_dir), html=False), name="frontend-static")
        template_files = {
            "login": frontend_dir / "login.html",
            "lobby": frontend_dir / "lobby.html",
            "my-bots": frontend_dir / "my-bots.html",
        }
        template_cache = {
            name: path.read_text(encoding="utf-8")
            for name, path in template_files.items()
            if path.exists()
        }

        def render_template(template_name: str) -> HTMLResponse:
            asset_version = os.getenv("APP_ASSET_VERSION", app.version)
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
            return render_template("lobby")

        @app.get("/my-bots", include_in_schema=False)
        def serve_my_bots(request: Request) -> Response:
            if not is_authenticated(request):
                return RedirectResponse(url="/login", status_code=302)
            return render_template("my-bots")

    return app


app = create_app()
