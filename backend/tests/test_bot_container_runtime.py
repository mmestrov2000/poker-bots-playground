import json

from app.bots.config import BotExecutionConfig
from app.bots.container_runtime import DockerBotRunner


class FakeResult:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_docker_bot_runner_start_and_stop(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        calls.append(cmd)
        if cmd[1] == "run":
            return FakeResult(stdout="container-123\n")
        if cmd[1] == "port":
            return FakeResult(stdout="0.0.0.0:49153\n")
        if cmd[1] == "rm":
            return FakeResult()
        return FakeResult()

    monkeypatch.setattr("app.bots.container_runtime.subprocess.run", fake_run)

    config = BotExecutionConfig(
        mode="docker",
        container_host="127.0.0.1",
        container_timeout_seconds=1.0,
        container_cpu=0.5,
        container_memory="256m",
        container_pids_limit=64,
        container_network=None,
        docker_bin="docker",
        container_port=8080,
    )
    runner = DockerBotRunner(
        bot_id="bot1",
        image_tag="poker-bot:bot1",
        entrypoint="bot.py",
        config=config,
    )
    info = runner.start()
    assert info.port == 49153
    assert runner.container_id == "container-123"
    runner.stop()
    assert runner.container_id is None
    assert any(cmd[1] == "run" for cmd in calls)


def test_docker_bot_runner_act(monkeypatch) -> None:
    def fake_run(cmd, check=True, capture_output=True, text=True):
        if cmd[1] == "run":
            return FakeResult(stdout="container-456\n")
        if cmd[1] == "port":
            return FakeResult(stdout="0.0.0.0:49154\n")
        if cmd[1] == "rm":
            return FakeResult()
        return FakeResult()

    monkeypatch.setattr("app.bots.container_runtime.subprocess.run", fake_run)
    monkeypatch.setattr(
        "app.bots.container_runtime.url_request.urlopen",
        lambda *args, **kwargs: FakeResponse({"action": "check", "amount": 0}),
    )

    config = BotExecutionConfig(
        mode="docker",
        container_host="127.0.0.1",
        container_timeout_seconds=1.0,
        container_cpu=0.5,
        container_memory="256m",
        container_pids_limit=64,
        container_network=None,
        docker_bin="docker",
        container_port=8080,
    )
    runner = DockerBotRunner(
        bot_id="bot2",
        image_tag="poker-bot:bot2",
        entrypoint="bot.py",
        config=config,
    )
    runner.start()
    result = runner.act({"legal_actions": ["check"]})
    assert result["action"] == "check"
