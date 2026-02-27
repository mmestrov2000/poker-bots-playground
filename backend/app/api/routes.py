import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.auth.config import AuthSettings
from app.auth.service import AuthError, AuthLockedError, AuthService
from app.auth.store import AuthStore
from app.bots.loader import BotLoadError, save_upload
from app.bots.security import MAX_UPLOAD_BYTES
from app.bots.validator import validate_bot_archive
from app.engine.game import SEAT_ORDER
from app.services.match_service import HandRecord, MatchService
from app.storage.hand_store import HandStore


router = APIRouter()
repo_root = Path(__file__).resolve().parents[3]
uploads_dir = repo_root / "runtime" / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)

auth_settings = AuthSettings.from_env(repo_root=repo_root)
auth_service = AuthService(store=AuthStore(auth_settings.db_path), settings=auth_settings)


def _update_persistent_leaderboard(hand: HandRecord, seat_bot_ids: dict[str, str]) -> None:
    big_blind = match_service.engine.big_blind_cents / 100
    if big_blind <= 0:
        return

    updated_at = int(hand.completed_at.timestamp())
    for seat_id in hand.active_seats:
        bot_id = seat_bot_ids.get(seat_id)
        if bot_id is None:
            continue
        delta_bb = hand.deltas.get(seat_id, 0.0) / big_blind
        existing = auth_service.store.get_leaderboard_row(bot_id)
        hands_played = (existing["hands_played"] if existing else 0) + 1
        bb_won = (existing["bb_won"] if existing else 0.0) + delta_bb
        auth_service.store.upsert_leaderboard_row(
            bot_id=bot_id,
            hands_played=hands_played,
            bb_won=bb_won,
            updated_at=updated_at,
        )


match_service = MatchService(hand_store=HandStore(), on_hand_completed=_update_persistent_leaderboard)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=1024)


class SelectBotRequest(BaseModel):
    bot_id: str = Field(min_length=1, max_length=128)


class CreateLobbyTableRequest(BaseModel):
    small_blind: float = Field(gt=0)
    big_blind: float = Field(gt=0)


def _should_set_secure_cookie(request: Request) -> bool:
    if auth_settings.session_cookie_secure is not None:
        return auth_settings.session_cookie_secure

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    scheme = forwarded_proto or request.url.scheme
    if scheme == "https":
        return True

    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    hostname = host.split(",")[0].strip().split(":")[0].lower()
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return False

    # Fail secure-by-default for non-local hosts when request scheme can't be trusted.
    return True


def require_authenticated_user(request: Request) -> dict:
    session_id = request.cookies.get(auth_settings.session_cookie_name)
    user = auth_service.get_user_from_session(session_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _format_bot_for_response(bot: dict) -> dict:
    created_at = datetime.fromtimestamp(bot["created_at"], tz=timezone.utc).isoformat()
    return {
        "bot_id": bot["bot_id"],
        "owner_user_id": bot["owner_user_id"],
        "name": bot["name"],
        "version": bot["version"],
        "status": "ready",
        "created_at": created_at,
    }


def _format_table_for_response(record: dict) -> dict:
    created_at = datetime.fromtimestamp(record["created_at"], tz=timezone.utc).isoformat()
    return {
        "table_id": record["table_id"],
        "small_blind": float(record["small_blind"]),
        "big_blind": float(record["big_blind"]),
        "status": record["status"],
        "seats_filled": 0,
        "max_seats": len(SEAT_ORDER),
        "created_at": created_at,
    }


def _format_leaderboard_row(row: dict) -> dict:
    bot = auth_service.store.get_bot_record(row["bot_id"])
    owner = auth_service.store.get_user_by_id(bot["owner_user_id"]) if bot is not None else None
    updated_at_iso = datetime.fromtimestamp(row["updated_at"], tz=timezone.utc).isoformat()
    return {
        "bot_id": row["bot_id"],
        "bot_name": bot["name"] if bot is not None else None,
        "bot_version": bot["version"] if bot is not None else None,
        "owner_user_id": bot["owner_user_id"] if bot is not None else None,
        "owner_username": owner["username"] if owner is not None else None,
        "hands_played": row["hands_played"],
        "bb_won": row["bb_won"],
        "bb_per_hand": row["bb_per_hand"],
        "updated_at": updated_at_iso,
    }


def require_owned_bot(bot_id: str, current_user: dict) -> dict:
    bot = auth_service.store.get_bot_record(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot["owner_user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return bot


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response, request: Request) -> dict:
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
        secure=_should_set_secure_cookie(request),
        samesite="lax",
        max_age=auth_settings.session_ttl_seconds,
        path="/",
    )
    return {"user": user}


@router.post("/auth/register")
def register(payload: RegisterRequest, response: Response, request: Request) -> dict:
    try:
        user, session = auth_service.register(username=payload.username, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response.set_cookie(
        key=auth_settings.session_cookie_name,
        value=session["session_id"],
        httponly=True,
        secure=_should_set_secure_cookie(request),
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
    records = auth_service.store.list_bot_records_by_owner(current_user["user_id"])
    bots = [_format_bot_for_response(record) for record in records]
    return {"bots": bots, "user": current_user}


@router.post("/my/bots")
async def upload_my_bot(
    current_user: dict = Depends(require_authenticated_user),
    bot_file: UploadFile = File(...),
    name: str = Form(...),
    version: str = Form(...),
) -> dict:
    bot_name = name.strip()
    if not bot_name:
        raise HTTPException(status_code=400, detail="name is required")
    if len(bot_name) > 120:
        raise HTTPException(status_code=400, detail="name must be at most 120 characters")

    bot_version = version.strip()
    if not bot_version:
        raise HTTPException(status_code=400, detail="version is required")
    if len(bot_version) > 64:
        raise HTTPException(status_code=400, detail="version must be at most 64 characters")

    filename = bot_file.filename or "bot.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip bot uploads are supported")

    payload = await bot_file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 10MB limit")

    is_valid, error_message = validate_bot_archive(payload)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message or "Invalid bot archive")

    bot_id = uuid4().hex
    user_upload_dir = uploads_dir / "users" / current_user["user_id"]
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    bot_path = save_upload(
        seat_id=bot_id,
        filename=filename,
        payload=payload,
        uploads_dir=user_upload_dir,
    )

    record = auth_service.store.create_bot_record(
        bot_id=bot_id,
        owner_user_id=current_user["user_id"],
        name=bot_name,
        version=bot_version,
        artifact_path=str(bot_path),
        now_ts=int(datetime.now(tz=timezone.utc).timestamp()),
    )
    return {"bot": _format_bot_for_response(record)}


@router.get("/lobby/tables")
def list_lobby_tables(current_user: dict = Depends(require_authenticated_user)) -> dict:
    records = auth_service.store.list_table_records()
    tables = [_format_table_for_response(record) for record in records]
    return {"tables": tables, "user": current_user}


@router.post("/lobby/tables")
def create_lobby_table(
    payload: CreateLobbyTableRequest,
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    small_blind = float(payload.small_blind)
    big_blind = float(payload.big_blind)
    if big_blind <= small_blind:
        raise HTTPException(status_code=400, detail="big_blind must be greater than small_blind")

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    record = auth_service.store.create_table_record(
        table_id=uuid4().hex,
        created_by_user_id=current_user["user_id"],
        small_blind=small_blind,
        big_blind=big_blind,
        status="waiting",
        now_ts=now_ts,
    )
    return {"table": _format_table_for_response(record), "user": current_user}


@router.get("/lobby/leaderboard")
def get_lobby_leaderboard(current_user: dict = Depends(require_authenticated_user)) -> dict:
    rows = auth_service.store.list_leaderboard_rows()
    leaderboard = [_format_leaderboard_row(row) for row in rows]
    return {"leaderboard": leaderboard, "user": current_user}


@router.post("/tables/{table_id}/seats/{seat_id}/bot-select")
def select_bot_for_seat(
    table_id: str,
    seat_id: str,
    payload: SelectBotRequest | None = Body(default=None),
    current_user: dict = Depends(require_authenticated_user),
) -> dict:
    normalized_seat = seat_id.upper()
    if normalized_seat not in set(SEAT_ORDER):
        raise HTTPException(status_code=400, detail="seat_id must be 1-6")
    if payload is None:
        raise HTTPException(status_code=400, detail="bot_id is required")

    bot = require_owned_bot(payload.bot_id, current_user=current_user)
    artifact_path = Path(bot["artifact_path"])
    if not artifact_path.exists():
        raise HTTPException(status_code=400, detail="Bot artifact is unavailable")

    try:
        seat = match_service.register_bot(
            normalized_seat,
            bot["name"],
            bot_path=artifact_path,
            bot_id=bot["bot_id"],
        )
    except BotLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"seat": seat, "match": match_service.get_match(), "bot": _format_bot_for_response(bot)}


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
