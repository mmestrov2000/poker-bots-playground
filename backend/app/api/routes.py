from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.bots.loader import save_upload
from app.services.match_service import MatchService
from app.storage.hand_store import HandStore


router = APIRouter()
repo_root = Path(__file__).resolve().parents[3]
uploads_dir = repo_root / "runtime" / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)

match_service = MatchService(hand_store=HandStore())


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/seats")
def get_seats() -> dict:
    return {"seats": match_service.get_seats()}


@router.post("/seats/{seat_id}/bot")
async def upload_bot(seat_id: str, bot_file: UploadFile = File(...)) -> dict:
    normalized_seat = seat_id.upper()
    if normalized_seat not in {"A", "B"}:
        raise HTTPException(status_code=400, detail="seat_id must be A or B")

    filename = bot_file.filename or "bot.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip bot uploads are supported")

    payload = await bot_file.read()
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Upload exceeds 10MB limit")

    save_upload(
        seat_id=normalized_seat,
        filename=filename,
        payload=payload,
        uploads_dir=uploads_dir,
    )

    seat = match_service.register_bot(normalized_seat, filename)
    return {"seat": seat, "match": match_service.get_match()}


@router.get("/match")
def get_match() -> dict:
    return {"match": match_service.get_match()}


@router.post("/match/reset")
def reset_match() -> dict:
    match_service.reset_match()
    return {"match": match_service.get_match()}


@router.get("/hands")
def list_hands(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    return {"hands": match_service.list_hands(limit=limit)}


@router.get("/hands/{hand_id}")
def get_hand(hand_id: str) -> dict:
    hand = match_service.get_hand(hand_id)
    if hand is None:
        raise HTTPException(status_code=404, detail="Hand not found")
    return hand
