import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from wrapper.claude_cli import (
    ClaudeFailed,
    ClaudeReply,
    ClaudeTimedOut,
    TokenError,
    build_system_prompt,
    read_token,
    run_claude,
)
from wrapper.openai_chat import (
    TOOL_NAME,
    ChatRequest,
    join_conversation,
    join_system_messages,
    tool_call_response,
)


def read_token_or_exit() -> str:
    try:
        return read_token()
    except TokenError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None


CLAUDE_TOKEN = read_token_or_exit()
app = FastAPI()


def error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message}})


@app.post("/v1/chat/completions", response_model=None)
def chat_completions(body: ChatRequest) -> JSONResponse | dict[str, object]:
    if body.stream:
        return error_response(400, "streaming is not supported")
    if [tool.function.name for tool in body.tools] != [TOOL_NAME]:
        return error_response(400, f"only the {TOOL_NAME} tool is supported")
    system_prompt = build_system_prompt(
        join_system_messages(body.messages), body.tools[0].function.parameters
    )
    result = run_claude(join_conversation(body.messages), system_prompt, body.model, CLAUDE_TOKEN)
    match result:
        case ClaudeReply(text=text):
            return tool_call_response(body.model, text)
        case ClaudeFailed(reason=reason):
            return error_response(502, reason)
        case ClaudeTimedOut(seconds=seconds):
            return error_response(504, f"claude -p timed out after {seconds} s")
