import itertools
import logging
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from wrapper.claude_cli import (
    ClaudeFailed,
    ClaudeReply,
    ClaudeTimedOut,
    ProcessKey,
    SpareProcess,
    TokenError,
    ask_claude,
    build_system_prompt,
    read_token,
)
from wrapper.openai_chat import (
    TOOL_NAME,
    ChatRequest,
    join_conversation,
    join_system_messages,
    tool_call_response,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
log = logging.getLogger("wrapper")


def read_token_or_exit() -> str:
    try:
        return read_token()
    except TokenError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None


SPARE = SpareProcess(read_token_or_exit())
REQUEST_IDS = itertools.count(1)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    yield
    SPARE.close()
    log.info("spare stopped")


app = FastAPI(lifespan=lifespan)


def error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message}})


def one_line(text: str) -> str:
    return " ".join(text.split())


@app.post("/v1/chat/completions", response_model=None)
def chat_completions(body: ChatRequest) -> JSONResponse | dict[str, object]:
    request_id = next(REQUEST_IDS)
    if body.stream:
        log.info("req %d rejected: streaming is not supported", request_id)
        return error_response(400, "streaming is not supported")
    if [tool.function.name for tool in body.tools] != [TOOL_NAME]:
        log.info("req %d rejected: tools %s", request_id, [tool.function.name for tool in body.tools])
        return error_response(400, f"only the {TOOL_NAME} tool is supported")
    key = ProcessKey(
        body.model,
        build_system_prompt(join_system_messages(body.messages), body.tools[0].function.parameters),
    )
    prompt = join_conversation(body.messages)
    log.info(
        "req %d received model=%s prompt=%d chars system=%d chars messages=%d",
        request_id, body.model, len(prompt), len(key.system_prompt), len(body.messages),
    )
    started = time.monotonic()
    try:
        checkout = SPARE.check_out(key)
        SPARE.refill(key)
    except OSError as error:
        log.info("req %d failed: could not start claude: %s", request_id, error.strerror)
        return error_response(502, f"could not start claude: {error.strerror}")
    kind = "warm process" if checkout.warm else "cold start"
    log.info("req %d %s (%s), spare started for the next request", request_id, kind, checkout.note)
    result = ask_claude(checkout.claude, prompt)
    seconds = time.monotonic() - started
    match result:
        case ClaudeReply(text=text):
            log.info("req %d reply in %.1f s: %s", request_id, seconds, one_line(text))
            return tool_call_response(body.model, text)
        case ClaudeFailed(reason=reason):
            log.info("req %d failed in %.1f s: %s", request_id, seconds, one_line(reason))
            return error_response(502, reason)
        case ClaudeTimedOut(seconds=limit):
            log.info("req %d timed out after %d s", request_id, limit)
            return error_response(504, f"claude -p timed out after {limit} s")
