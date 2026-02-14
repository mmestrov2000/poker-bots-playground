from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api import routes
from app.auth.config import AuthSettings
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.services.match_service import MatchService
from app.storage.hand_store import HandStore


@pytest.fixture(autouse=True)
def isolate_route_state(tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    settings = AuthSettings(
        session_cookie_name="ppg_session",
        session_cookie_secure=None,
        session_ttl_seconds=3600,
        login_max_failures=3,
        login_lockout_seconds=60,
        login_failure_window_seconds=300,
        bootstrap_username="bootstrap",
        bootstrap_password="bootstrap-password",
        db_path=Path(tmp_path / "auth.sqlite3"),
    )
    auth_service = AuthService(store=AuthStore(settings.db_path), settings=settings)
    auth_service.ensure_user("alice", "correct-horse-battery-staple")

    monkeypatch.setattr(routes, "uploads_dir", uploads_dir)
    monkeypatch.setattr(routes, "match_service", MatchService(hand_store=HandStore(base_dir=tmp_path / "hands")))
    monkeypatch.setattr(routes, "auth_settings", settings)
    monkeypatch.setattr(routes, "auth_service", auth_service)


def build_request_with_cookies(cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    headers.append((b"host", b"localhost"))
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    scope = {
        "type": "http",
        "asgi.version": "3.0",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def extract_session_cookie(response: Response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie[routes.auth_settings.session_cookie_name]
    return morsel.value


def test_frontend_pages_split_login_lobby_and_my_bots():
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    login_html = (frontend_dir / "login.html").read_text(encoding="utf-8")
    lobby_html = (frontend_dir / "lobby.html").read_text(encoding="utf-8")
    my_bots_html = (frontend_dir / "my-bots.html").read_text(encoding="utf-8")

    assert 'id="auth-form"' in login_html
    assert 'id="auth-mode-login"' in login_html
    assert 'id="auth-mode-register"' in login_html
    assert "/static/login.js" in login_html

    assert 'id="nav-lobby"' in lobby_html
    assert 'id="nav-my-bots"' in lobby_html
    assert 'id="logout-button"' in lobby_html
    assert 'href="/lobby"' in lobby_html
    assert 'href="/my-bots"' in lobby_html
    assert "/static/lobby.js" in lobby_html

    # Existing table UX controls remain available on the Lobby page.
    assert 'id="seat-1-take"' in lobby_html
    assert 'id="seat-6-take"' in lobby_html
    assert 'id="start-match"' in lobby_html

    assert 'id="my-bots-list"' in my_bots_html
    assert 'id="my-bots-upload-form"' in my_bots_html
    assert 'id="bot-name"' in my_bots_html
    assert 'id="bot-version"' in my_bots_html
    assert 'id="bot-file"' in my_bots_html
    assert 'id="my-bots-upload-submit"' in my_bots_html
    assert 'id="my-bots-upload-feedback"' in my_bots_html
    assert 'id="my-bots-state"' in my_bots_html
    assert "/static/my-bots.js" in my_bots_html


def test_frontend_route_guard_login_logout_navigation_smoke():
    with pytest.raises(HTTPException) as unauthorized:
        routes.require_authenticated_user(build_request_with_cookies())
    assert unauthorized.value.status_code == 401

    login_response = Response()
    login_result = routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        login_response,
        build_request_with_cookies(),
    )
    assert login_result["user"]["username"] == "alice"
    session_id = extract_session_cookie(login_response)

    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    current_user = routes.require_authenticated_user(request)
    assert current_user["username"] == "alice"

    lobby = routes.list_lobby_tables(current_user=current_user)
    my_bots = routes.list_my_bots(current_user=current_user)
    assert lobby["user"]["username"] == "alice"
    assert my_bots["user"]["username"] == "alice"

    logout_response = Response()
    logout_result = routes.logout(request, logout_response)
    assert logout_result["ok"] is True

    with pytest.raises(HTTPException) as unauthorized_after_logout:
        routes.require_authenticated_user(request)
    assert unauthorized_after_logout.value.status_code == 401


def test_frontend_register_smoke_and_duplicate_username_guard():
    register_response = Response()
    register_result = routes.register(
        routes.RegisterRequest(username="new-player", password="new-password"),
        register_response,
        build_request_with_cookies(),
    )
    assert register_result["user"]["username"] == "new-player"
    session_id = extract_session_cookie(register_response)
    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    current_user = routes.require_authenticated_user(request)
    assert current_user["username"] == "new-player"

    with pytest.raises(HTTPException) as duplicate_error:
        routes.register(
            routes.RegisterRequest(username="new-player", password="different-password"),
            Response(),
            build_request_with_cookies(),
        )
    assert duplicate_error.value.status_code == 409


def test_frontend_my_bots_script_smoke_for_page_load_upload_and_states():
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    my_bots_js = (frontend_dir / "my-bots.js").read_text(encoding="utf-8")

    # Authenticated page bootstrap and data load.
    assert "window.AppShell.getCurrentUser()" in my_bots_js
    assert 'window.AppShell.initHeader("my-bots", user)' in my_bots_js
    assert 'window.AppShell.request("/my/bots")' in my_bots_js

    # Upload success flow and post-upload reconciliation.
    assert 'window.AppShell.request("/my/bots", {' in my_bots_js
    assert 'method: "POST"' in my_bots_js
    assert "Upload successful" in my_bots_js
    assert "await loadBots()" in my_bots_js

    # Error handling and explicit loading/empty/error states.
    assert "Loading bots..." in my_bots_js
    assert "No bots uploaded yet." in my_bots_js
    assert "Failed to load bots." in my_bots_js
    assert "Upload failed." in my_bots_js
