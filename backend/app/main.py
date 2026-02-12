import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.db.bootstrap import maybe_bootstrap_shared_schema


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
        index_template = (frontend_dir / "index.html").read_text(encoding="utf-8")

        @app.get("/", include_in_schema=False)
        @app.get("/index.html", include_in_schema=False)
        def serve_index() -> HTMLResponse:
            asset_version = os.getenv("APP_ASSET_VERSION", app.version)
            html = index_template.replace("__ASSET_VERSION__", asset_version)
            response = HTMLResponse(content=html)
            # Always revalidate HTML so browsers fetch the latest asset version token.
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            return response

    @app.on_event("startup")
    def bootstrap_shared_schema() -> None:
        maybe_bootstrap_shared_schema(repo_root=repo_root)

    return app


app = create_app()
