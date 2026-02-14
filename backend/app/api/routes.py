import math
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.auth.config import AuthSettings
from app.auth.service import AuthError, AuthLockedError, AuthService
from app.auth.store import AuthStore
from app.bots.loader import BotLoadError, save_upload
from app.bots.security import MAX_UPLOAD_BYTES
from app.bots.validator import validate_bot_archive
from app.engine.game import SEAT_ORDER
from app.services.match_service import MatchService
from app.storage.hand_store import HandStore


router = APIRouter()
repo_root = Path(__file__).resolve().parents[3]
uploads_dir = repo_root / "runtime" / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)

auth_settings = AuthSettings.from_env(repo_root=repo_root)
auth_service = AuthService(store=AuthStore(auth_settings.db_path), settings=auth_settings)
match_service = MatchService(hand_store=HandStore())


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


def require_authenticated_user(request: Request) -> dict:
    session_id = request.cookies.get(auth_settings.session_cookie_name)
    user = auth_service.get_user_from_session(session_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response) -> dict:
    try:
        user, session = auth_service.login(username=payload.username, password=payload.password)
    except AuthLockedError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Too many failed login attempts",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        ) from exc
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    response.set_cookie(
        key=auth_settings.session_cookie_name,
        value=session["session_id"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=auth_settings.session_ttl_seconds,
        path="/",
    )
    return {"user": user}


@router.post("/auth/register")
def register(payload: RegisterRequest, response: Response) -> dict:
    try:
        user, session = auth_service.register(username=payload.username, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response.set_cookie(
        key=auth_settings.session_cookie_name,
        value=session["session_id"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=auth_settings.session_ttl_seconds,
        path="/",
    )
    return {"user": user}


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    session_id = request.cookies.get(auth_settings.session_cookie_name)
    auth_service.logout(session_id)
    response.delete_cookie(key=auth_settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(current_user: dict = Depends(require_authenticated_user)) -> dict:
    return {"user": current_user}


@router.get("/my/bots")
def list_my_bots(current_user: dict = Depends(require_authenticated_user)) -> dict:
    return {"bots": [], "user": current_user}


@router.get("/lobby/tables")
def list_lobby_tables(current_user: dict = Depends(require_authenticated_user)) -> dict:
    return {"tables": [], "user": current_user}


@router.post("/lobby/tables")
def create_lobby_table(current_user: dict = Depends(require_authenticated_user)) -> dict:
    raise HTTPException(status_code=501, detail="Lobby table creation is not implemented yet")


@router.get("/lobby/leaderboard")
def get_lobby_leaderboard(current_user: dict = Depends(require_authenticated_user)) -> dict:
    return {"leaderboard": [], "user": current_user}


@router.post("/tables/{table_id}/seats/{seat_id}/bot-select")
def select_bot_for_seat(
    table_id: str,
    seat_id: str,
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    normalized_seat = seat_id.upper()
    if normalized_seat not in {"A", "B"}:
        raise HTTPException(status_code=400, detail="seat_id must be A or B")
    raise HTTPException(status_code=501, detail="Seat bot selection is not implemented yet")


@router.get("/seats")
def get_seats() -> dict:
    return {"seats": match_service.get_seats()}


@router.post("/seats/{seat_id}/bot")
async def upload_bot(seat_id: str, bot_file: UploadFile = File(...)) -> dict:
    normalized_seat = seat_id.upper()
    if normalized_seat not in set(SEAT_ORDER):
        raise HTTPException(status_code=400, detail="seat_id must be 1-6")

    filename = bot_file.filename or "bot.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip bot uploads are supported")

    payload = await bot_file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 10MB limit")

    is_valid, error_message = validate_bot_archive(payload)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message or "Invalid bot archive")

    bot_path = save_upload(
        seat_id=normalized_seat,
        filename=filename,
        payload=payload,
        uploads_dir=uploads_dir,
    )

    try:
        seat = match_service.register_bot(normalized_seat, filename, bot_path=bot_path)
    except BotLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"seat": seat, "match": match_service.get_match()}


@router.get("/match")
def get_match() -> dict:
    return {"match": match_service.get_match()}


@router.post("/match/start")
def start_match() -> dict:
    try:
        match_service.start_match()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"match": match_service.get_match()}


@router.post("/match/pause")
def pause_match() -> dict:
    try:
        match_service.pause_match()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"match": match_service.get_match()}


@router.post("/match/resume")
def resume_match() -> dict:
    try:
        match_service.resume_match()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"match": match_service.get_match()}


@router.post("/match/end")
def end_match() -> dict:
    try:
        match_service.end_match()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"match": match_service.get_match()}


@router.post("/match/reset")
def reset_match() -> dict:
    match_service.reset_match()
    return {"match": match_service.get_match()}


@router.get("/hands")
def list_hands(
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=1000)] = 100,
    max_hand_id: Annotated[int | None, Query(ge=0)] = None,
) -> dict:
    if limit is not None:
        page_size = limit
        page = 1
    hands = match_service.list_hands(limit=limit, page=page, page_size=page_size, max_hand_id=max_hand_id)
    total_hands = match_service.get_match()["hands_played"]
    if max_hand_id is not None:
        total_hands = min(max_hand_id, total_hands)
    total_pages = math.ceil(total_hands / page_size) if total_hands else 0
    return {
        "hands": hands,
        "page": page,
        "page_size": page_size,
        "total_hands": total_hands,
        "total_pages": total_pages,
    }


@router.get("/pnl")
def get_pnl(
    since_hand_id: Annotated[int | None, Query(ge=0)] = None,
) -> dict:
    entries, last_hand_id = match_service.list_pnl(since_hand_id=since_hand_id)
    return {"entries": entries, "last_hand_id": last_hand_id}


@router.get("/leaderboard")
def get_leaderboard() -> dict:
    return match_service.get_leaderboard()


@router.get("/hands/{hand_id}")
def get_hand(hand_id: str) -> dict:
    hand = match_service.get_hand(hand_id)
    if hand is None:
        raise HTTPException(status_code=404, detail="Hand not found")
    return hand
