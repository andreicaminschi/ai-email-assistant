import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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


def build_command(model: str, system_prompt: str) -> list[str]:
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "text",
    ]


def build_environment(token: str) -> dict[str, str]:
    inherited = {
        name: value for name, value in os.environ.items() if name not in API_KEY_VARIABLES
    }
    return {**inherited, "CLAUDE_CODE_OAUTH_TOKEN": token}


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_claude(prompt: str, system_prompt: str, model: str, token: str) -> ClaudeResult:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as empty_dir:
        try:
            process = subprocess.Popen(
                build_command(model, system_prompt),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=empty_dir,
                env=build_environment(token),
                start_new_session=True,
            )
        except OSError as error:
            return ClaudeFailed(f"could not start claude: {error.strerror}")
        try:
            stdout, stderr = process.communicate(prompt, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            kill_process_tree(process)
            process.communicate()
            return ClaudeTimedOut(TIMEOUT_SECONDS)
    if process.returncode != 0:
        output = stderr.strip() or stdout.strip()
        return ClaudeFailed(f"claude -p exited {process.returncode}: {output}")
    return ClaudeReply(stdout.strip())
