from http.cookies import SimpleCookie
import io
from pathlib import Path
import zipfile

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api import routes
from app.auth.config import AuthSettings
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.main import create_app
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


def build_page_request(path: str, cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = [(b"host", b"localhost")]
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    scope = {
        "type": "http",
        "asgi.version": "3.0",
        "scheme": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def extract_session_cookie(response: Response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie[routes.auth_settings.session_cookie_name]
    return morsel.value


def build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeUploadFile:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def get_page_endpoint(path: str):
    app = create_app()
    for route in app.routes:
        if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"Missing GET route for {path}")


def test_frontend_pages_split_login_lobby_and_my_bots():
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    login_html = (frontend_dir / "login.html").read_text(encoding="utf-8")
    lobby_html = (frontend_dir / "lobby.html").read_text(encoding="utf-8")
    table_detail_html = (frontend_dir / "table-detail.html").read_text(encoding="utf-8")
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

    # Lobby page renders list/create controls and leaderboard panel.
    assert 'id="create-table-form"' in lobby_html
    assert 'id="create-small-blind"' in lobby_html
    assert 'id="create-big-blind"' in lobby_html
    assert 'id="create-table-feedback"' in lobby_html
    assert 'id="lobby-tables-state"' in lobby_html
    assert 'id="lobby-tables-body"' in lobby_html
    assert 'id="lobby-leaderboard-state"' in lobby_html
    assert 'id="lobby-leaderboard-list"' in lobby_html

    # Table detail page renders the live gameplay experience.
    assert 'id="table-id-label"' in table_detail_html
    assert 'id="seat-1-name"' in table_detail_html
    assert 'id="seat-6-name"' in table_detail_html
    assert 'id="start-match"' in table_detail_html
    assert 'id="hands-list"' in table_detail_html
    assert 'id="hand-detail"' in table_detail_html
    assert 'id="pnl-chart"' in table_detail_html
    assert 'id="leaderboard-list"' in table_detail_html
    assert "/static/table-detail.js" in table_detail_html

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


def test_frontend_lobby_script_smoke_for_seat_select_and_inline_create():
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    lobby_js = (frontend_dir / "lobby.js").read_text(encoding="utf-8")

    assert 'window.AppShell.request("/lobby/tables")' in lobby_js
    assert 'window.AppShell.request("/lobby/tables", {' in lobby_js
    assert 'window.AppShell.request("/lobby/leaderboard")' in lobby_js
    assert "setCreateSubmitting(true);" in lobby_js
    assert "setCreateSubmitting(false);" in lobby_js
    assert "Table created successfully. It is now listed below." in lobby_js
    assert "await refreshTablesOnly();" in lobby_js
    assert "knownTables = [normalizedTable" in lobby_js
    assert 'const tableId = table.table_id || table.tableId || "unknown";' in lobby_js
    assert "const candidates = [table.seats_filled, table.seatsFilled, table.ready_seats, table.readySeats];" in lobby_js
    assert 'return table.state || table.status || "waiting";' in lobby_js
    assert 'showCreateFeedback("Big blind must be greater than small blind.", "error");' in lobby_js
    assert 'tablesState.textContent = "Failed to load tables."' in lobby_js
    assert 'leaderboardState.textContent = "Failed to load leaderboard."' in lobby_js
    assert "refreshLobbyData().catch((error) => {" in lobby_js
    assert "window.setInterval(() => {" in lobby_js
    assert "window.clearInterval(refreshTimer);" in lobby_js


def test_frontend_table_detail_script_smoke_for_table_route_and_live_interactions():
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    table_detail_js = (frontend_dir / "table-detail.js").read_text(encoding="utf-8")

    assert "window.location.pathname.match(/^\\/tables\\/([^/]+)$/)" in table_detail_js
    assert "window.AppShell.request(`/tables/${encodeURIComponent(tableId)}/seats/${activeSeatId}/bot-select`" in table_detail_js
    assert "`/hands?${params.toString()}`" in table_detail_js
    assert "`/hands/${handId}`" in table_detail_js
    assert 'window.AppShell.request(`/pnl${query ? `?${query}` : ""}`)' in table_detail_js
    assert 'window.AppShell.request("/leaderboard")' in table_detail_js


def test_frontend_login_redirect_for_protected_pages():
    lobby_endpoint = get_page_endpoint("/lobby")
    my_bots_endpoint = get_page_endpoint("/my-bots")
    table_endpoint = get_page_endpoint("/tables/{table_id}")

    lobby = lobby_endpoint(build_page_request(path="/lobby"))
    assert lobby.status_code == 302
    assert lobby.headers["location"] == "/login"

    my_bots = my_bots_endpoint(build_page_request(path="/my-bots"))
    assert my_bots.status_code == 302
    assert my_bots.headers["location"] == "/login"

    table_detail = table_endpoint(build_page_request(path="/tables/table-123"), table_id="table-123")
    assert table_detail.status_code == 302
    assert table_detail.headers["location"] == "/login"


def test_frontend_my_bots_page_loads_for_authenticated_user():
    login_response = Response()
    routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        login_response,
        build_request_with_cookies(),
    )
    session_id = extract_session_cookie(login_response)
    page_request = build_page_request(
        path="/my-bots",
        cookies={routes.auth_settings.session_cookie_name: session_id},
    )
    page = get_page_endpoint("/my-bots")(page_request)
    assert page.status_code == 200
    body = page.body.decode("utf-8")
    assert 'id="my-bots-list"' in body
    assert 'id="my-bots-upload-form"' in body


def test_frontend_table_detail_page_loads_for_authenticated_user():
    login_response = Response()
    routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        login_response,
        build_request_with_cookies(),
    )
    session_id = extract_session_cookie(login_response)
    page_request = build_page_request(
        path="/tables/table-123",
        cookies={routes.auth_settings.session_cookie_name: session_id},
    )
    page = get_page_endpoint("/tables/{table_id}")(page_request, table_id="table-123")
    assert page.status_code == 200
    body = page.body.decode("utf-8")
    assert 'id="table-id-label"' in body
    assert 'id="seat-1-name"' in body
    assert 'id="hands-list"' in body


@pytest.mark.anyio
async def test_frontend_happy_path_upload_interaction():
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    upload = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=FakeUploadFile(filename="smoke.zip", payload=payload),
        name="Smoke Bot",
        version="1.0.0",
    )
    assert upload["bot"]["name"] == "Smoke Bot"

    listed = routes.list_my_bots(current_user=current_user)
    assert len(listed["bots"]) == 1
    assert listed["bots"][0]["bot_id"] == upload["bot"]["bot_id"]
