import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

TIMEOUT_SECONDS = 120
API_KEY_VARIABLES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
FIXED_LINE = (
    "Reply with one JSON object that matches the schema below. No code fences, no other text."
)


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class ClaudeReply:
    text: str


@dataclass(frozen=True)
class ClaudeFailed:
    reason: str


@dataclass(frozen=True)
class ClaudeTimedOut:
    seconds: int


type ClaudeResult = ClaudeReply | ClaudeFailed | ClaudeTimedOut


@dataclass(frozen=True)
class ProcessKey:
    model: str
    system_prompt: str


@dataclass(frozen=True)
class ClaudeProcess:
    key: ProcessKey
    process: subprocess.Popen[str]
    work_dir: tempfile.TemporaryDirectory[str]
    started_at: float


@dataclass(frozen=True)
class Checkout:
    claude: ClaudeProcess
    warm: bool
    note: str


def read_token() -> str:
    path = Path(os.environ.get("SECRETS_DIR", "/run/secrets")) / "claude_token"
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise TokenError(f"Claude token missing: {path}") from None
    except OSError as error:
        raise TokenError(f"Claude token unreadable: {path}: {error.strerror}") from None
    if not token:
        raise TokenError(f"Claude token empty: {path}")
    return token


def build_system_prompt(request_prompt: str, schema: Mapping[str, object]) -> str:
    parts = [FIXED_LINE, request_prompt, json.dumps(schema, indent=2)]
    return "\n\n".join(part for part in parts if part)


def build_command(key: ProcessKey) -> list[str]:
    return [
        "claude",
        "-p",
        "--model",
        key.model,
        "--system-prompt",
        key.system_prompt,
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def build_environment(token: str) -> dict[str, str]:
    inherited = {
        name: value for name, value in os.environ.items() if name not in API_KEY_VARIABLES
    }
    return {**inherited, "CLAUDE_CODE_OAUTH_TOKEN": token}


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def start_claude(key: ProcessKey, token: str) -> ClaudeProcess:
    work_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        process = subprocess.Popen(
            build_command(key),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=work_dir.name,
            env=build_environment(token),
            start_new_session=True,
        )
    except OSError:
        work_dir.cleanup()
        raise
    return ClaudeProcess(key=key, process=process, work_dir=work_dir, started_at=time.monotonic())


def stop_claude(claude: ClaudeProcess) -> None:
    kill_process_tree(claude.process)
    claude.process.communicate()
    claude.work_dir.cleanup()


def build_user_line(prompt: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n"


def read_result_event(stdout: str) -> dict[str, object] | None:
    """
    @example
    read_result_event('{"type":"system"}\\n{"type":"result","result":"{}"}')
    # → {"type": "result", "result": "{}"}
    """
    events: list[dict[str, object]] = []
    for line in stdout.splitlines():
        try:
            parsed: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        event = cast(dict[str, object], parsed)
        if event.get("type") == "result":
            events.append(event)
    return events[-1] if events else None


def ask_claude(claude: ClaudeProcess, prompt: str) -> ClaudeResult:
    try:
        stdout, stderr = claude.process.communicate(build_user_line(prompt), timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        stop_claude(claude)
        return ClaudeTimedOut(TIMEOUT_SECONDS)
    claude.work_dir.cleanup()
    result = read_result_event(stdout)
    if result is not None and not result.get("is_error"):
        return ClaudeReply(str(result.get("result", "")).strip())
    if result is not None:
        return ClaudeFailed(f"claude reported an error: {result.get('result') or result.get('subtype')}")
    output = stderr.strip() or stdout.strip()
    return ClaudeFailed(f"claude -p exited {claude.process.returncode}: {output}")


class SpareProcess:
    """One started claude process, waiting for the next request with the same key."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._lock = threading.Lock()
        self._spare: ClaudeProcess | None = None

    def check_out(self, key: ProcessKey) -> Checkout:
        with self._lock:
            spare, self._spare = self._spare, None
        if spare is None:
            return Checkout(start_claude(key, self._token), warm=False, note="no spare yet")
        if spare.key != key:
            stop_claude(spare)
            reason = "spare was for another model" if spare.key.model != key.model else "spare was for another prompt"
            return Checkout(start_claude(key, self._token), warm=False, note=reason)
        exit_code = spare.process.poll()
        if exit_code is not None:
            stop_claude(spare)
            return Checkout(start_claude(key, self._token), warm=False, note=f"spare had exited with {exit_code}")
        waited = time.monotonic() - spare.started_at
        return Checkout(spare, warm=True, note=f"started {waited:.1f} s ago")

    def refill(self, key: ProcessKey) -> ClaudeProcess:
        claude = start_claude(key, self._token)
        with self._lock:
            old, self._spare = self._spare, claude
        if old is not None:
            stop_claude(old)
        return claude

    def close(self) -> None:
        with self._lock:
            spare, self._spare = self._spare, None
        if spare is not None:
            stop_claude(spare)
