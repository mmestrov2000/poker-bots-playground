from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from app.bots.config import BotExecutionConfig


logger = logging.getLogger(__name__)


@dataclass
class ContainerInfo:
    container_id: str
    host: str
    port: int
    image_tag: str
    entrypoint: str


class DockerBotRunner:
    def __init__(
        self,
        *,
        bot_id: str,
        image_tag: str,
        entrypoint: str,
        config: BotExecutionConfig,
    ) -> None:
        self.bot_id = bot_id
        self.image_tag = image_tag
        self.entrypoint = entrypoint
        self.config = config
        self.container_id: str | None = None
        self.host = config.container_host
        self.port: int | None = None
        self.name = f"poker_bot_{bot_id}"

    def start(self) -> ContainerInfo:
        self.stop()
        cmd = [
            self.config.docker_bin,
            "run",
            "-d",
            "--rm",
            "--name",
            self.name,
            "--label",
            f"poker.bot_id={self.bot_id}",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--pids-limit",
            str(self.config.container_pids_limit),
            "--cpus",
            str(self.config.container_cpu),
            "--memory",
            self.config.container_memory,
            "--security-opt",
            "no-new-privileges",
            "-e",
            f"BOT_ENTRYPOINT={self.entrypoint}",
            "-p",
            f"0:{self.config.container_port}",
        ]
        if self.config.container_network:
            cmd += ["--network", self.config.container_network]
        cmd.append(self.image_tag)
        result = _run_docker(cmd)
        self.container_id = result.stdout.strip()
        self.port = _resolve_host_port(self.container_id, self.config.container_port, self.config.docker_bin)
        return self.info()

    def act(self, state: dict) -> dict:
        if not self.container_id or not self.port:
            return {"action": "fold", "amount": 0, "error": "container_not_running"}
        url = f"http://{self.host}:{self.port}/act"
        payload = json.dumps(state).encode("utf-8")
        req = url_request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            with url_request.urlopen(req, timeout=self.config.container_timeout_seconds) as response:
                body = response.read()
                data = json.loads(body.decode("utf-8"))
        except (url_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Bot container request failed", exc_info=True)
            return {"action": "fold", "amount": 0, "error": "container_error"}
        if not isinstance(data, dict):
            return {"action": "fold", "amount": 0, "error": "invalid_response"}
        return _normalize_response(data)

    def stop(self) -> None:
        target = self.container_id or self.name
        if not target:
            return
        result = _run_docker(
            [self.config.docker_bin, "rm", "-f", target],
            check=False,
        )
        if result.returncode != 0:
            logger.warning("Failed to stop container %s: %s", target, result.stderr)
        self.container_id = None
        self.port = None

    def info(self) -> ContainerInfo:
        if not self.container_id or not self.port:
            raise RuntimeError("Container not started")
        return ContainerInfo(
            container_id=self.container_id,
            host=self.host,
            port=self.port,
            image_tag=self.image_tag,
            entrypoint=self.entrypoint,
        )


def build_bot_image(
    *,
    repo_root: Path,
    build_context: Path,
    image_tag: str,
    docker_bin: str,
) -> None:
    dockerfile = repo_root / "runtime" / "bot_runner" / "Dockerfile"
    if not dockerfile.exists():
        raise FileNotFoundError(dockerfile)
    _run_docker(
        [
            docker_bin,
            "build",
            "-f",
            str(dockerfile),
            "-t",
            image_tag,
            str(build_context),
        ]
    )


def _run_docker(cmd: list[str], check: bool = True):
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)
    return result


def _resolve_host_port(container_id: str, container_port: int, docker_bin: str) -> int:
    result = _run_docker([docker_bin, "port", container_id, f"{container_port}/tcp"])
    output = result.stdout.strip().splitlines()
    if not output:
        raise RuntimeError("Failed to resolve container port")
    host_binding = output[0].strip()
    try:
        port_str = host_binding.rsplit(":", 1)[-1]
        return int(port_str)
    except ValueError as exc:
        raise RuntimeError(f"Invalid docker port output: {host_binding}") from exc


def _normalize_response(payload: dict[str, Any]) -> dict:
    action = payload.get("action")
    if not isinstance(action, str):
        return {"action": "fold", "amount": 0, "error": "invalid_response"}
    amount = payload.get("amount", 0)
    if not isinstance(amount, int):
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return {"action": "fold", "amount": 0, "error": "invalid_response"}
    return {"action": action, "amount": amount, **{k: v for k, v in payload.items() if k not in {"action", "amount"}}}
