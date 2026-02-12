import math
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.bots.artifacts import ArtifactStore
from app.bots.build import BotBuildError, build_bot_image_from_archive, inspect_bot_archive
from app.bots.config import get_artifact_config, get_bot_execution_config
from app.bots.container_runtime import DockerBotRunner
from app.bots.loader import BotLoadError
from app.bots.registry import BotRegistry, derive_bot_id
from app.bots.security import MAX_UPLOAD_BYTES
from app.bots.validator import validate_bot_archive
from app.db.config import get_db_config
from app.engine.game import SEAT_ORDER
from app.services.match_service import MatchService
from app.storage.hand_store import HandStore


router = APIRouter()
repo_root = Path(__file__).resolve().parents[3]
bot_registry = BotRegistry()
logger = logging.getLogger(__name__)
_shared_bootstrapped = False

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

    bot_id = derive_bot_id(filename, payload)
    artifact_store = ArtifactStore(get_artifact_config(repo_root))
    artifact_ref = artifact_store.store(bot_id=bot_id, filename=filename, payload=payload)
    artifact_path = artifact_store.fetch(artifact_ref)
    execution_config = get_bot_execution_config()
    db_config = get_db_config()
    bot_schema = f"{db_config.private_schema_prefix}{bot_id}"
    db_user = f"{bot_schema}_rw"
    registry_entry = bot_registry.ensure_entry(
        bot_id=bot_id,
        bot_name=filename,
        schema=bot_schema,
        db_user=db_user,
    )
    bot_registry.update_entry(
        bot_id,
        {
            "artifact": artifact_ref.to_dict(),
            "artifact_sha256": artifact_ref.sha256,
            "artifact_size_bytes": artifact_ref.size_bytes,
        },
    )
    bot_runner = None
    try:
        if execution_config.mode == "docker":
            image_tag = f"poker-bot:{bot_id}-{artifact_ref.sha256[:8]}"
            build_info = build_bot_image_from_archive(
                artifact_path=artifact_path,
                repo_root=repo_root,
                image_tag=image_tag,
                docker_bin=execution_config.docker_bin,
            )
            bot_runner = DockerBotRunner(
                bot_id=bot_id,
                image_tag=image_tag,
                entrypoint=build_info.entrypoint,
                config=execution_config,
            )
            container_info = bot_runner.start()
            bot_registry.update_entry(
                bot_id,
                {
                    "image_tag": image_tag,
                    "requirements_hash": build_info.requirements_hash,
                    "container_id": container_info.container_id,
                    "container_host": container_info.host,
                    "container_port": container_info.port,
                    "bot_entrypoint": build_info.entrypoint,
                },
            )
        else:
            archive_info = inspect_bot_archive(artifact_path)
            bot_registry.update_entry(
                bot_id,
                {
                    "image_tag": None,
                    "requirements_hash": archive_info.requirements_hash,
                    "container_id": None,
                    "container_host": None,
                    "container_port": None,
                    "bot_entrypoint": archive_info.entrypoint,
                },
            )
    except BotBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        logger.warning("Bot container build failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start bot container") from exc
    try:
        seat = match_service.register_bot(
            normalized_seat,
            filename,
            bot_path=None if bot_runner else artifact_path,
            bot_id=bot_id,
            bot_runner=bot_runner,
        )
    except BotLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _maybe_bootstrap_db(db_config, registry_entry)
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


@router.get("/bots/{bot_id}/db-info")
def get_db_info(bot_id: str) -> dict:
    entry = bot_registry.get(bot_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Bot not found")
    db_config = get_db_config()
    return {
        "enabled": db_config.enabled,
        "host": db_config.host,
        "port": db_config.port,
        "name": db_config.name,
        "schema": entry["schema"],
        "shared_schema": db_config.shared_schema,
        "user": entry["db_user"],
        "password": entry["db_password"],
        "sslmode": db_config.sslmode,
    }


def _maybe_bootstrap_db(db_config, entry: dict) -> None:
    global _shared_bootstrapped
    if not db_config.enabled:
        return
    script_path = repo_root / "backend" / "scripts" / "db_bootstrap.py"
    if not script_path.exists():
        logger.warning("db_bootstrap.py not found; skipping bootstrap")
        return
    env = os.environ.copy()
    if db_config.shared_aggregator_user:
        env["DB_SHARED_AGGREGATOR_USER"] = db_config.shared_aggregator_user
    if db_config.shared_aggregator_password:
        env["DB_SHARED_AGGREGATOR_PASSWORD"] = db_config.shared_aggregator_password
    try:
        if not _shared_bootstrapped:
            shared_cmd = [sys.executable, str(script_path), "--shared"]
            if db_config.shared_aggregator_password:
                shared_cmd += [
                    "--shared-aggregator-password",
                    db_config.shared_aggregator_password,
                ]
            subprocess.run(shared_cmd, check=True, cwd=str(repo_root), env=env)
            _shared_bootstrapped = True
        subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--bot-id",
                entry["bot_id"],
                "--bot-password",
                entry["db_password"],
            ],
            check=True,
            cwd=str(repo_root),
            env=env,
        )
    except Exception:
        logger.warning("DB bootstrap failed", exc_info=True)
