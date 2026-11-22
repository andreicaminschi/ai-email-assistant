import time
from uuid import uuid4

from pydantic import BaseModel, Field

TOOL_NAME = "final_result"
SYSTEM_ROLES = ("system", "developer")
ROLE_TAGS = {"user": "User", "assistant": "Assistant", "tool": "Tool"}


class FunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    function: FunctionCall


class TextPart(BaseModel):
    type: str
    text: str = ""


class Message(BaseModel):
    role: str
    content: str | list[TextPart] | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list[ToolCall])


class FunctionSpec(BaseModel):
    name: str
    parameters: dict[str, object] = Field(default_factory=dict[str, object])


class Tool(BaseModel):
    function: FunctionSpec


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    tools: list[Tool] = Field(default_factory=list[Tool])
    stream: bool = False


def message_text(message: Message) -> str:
    if isinstance(message.content, list):
        content = "\n".join(part.text for part in message.content if part.text)
    else:
        content = message.content or ""
    calls = [call.function.arguments for call in message.tool_calls]
    return "\n".join(part for part in [content, *calls] if part)


def join_system_messages(messages: list[Message]) -> str:
    return "\n\n".join(
        message_text(message) for message in messages if message.role in SYSTEM_ROLES
    )


def join_conversation(messages: list[Message]) -> str:
    return "\n\n".join(
        f"{ROLE_TAGS.get(message.role, message.role.title())}: {message_text(message)}"
        for message in messages
        if message.role not in SYSTEM_ROLES
    )


def tool_call_response(model: str, arguments: str) -> dict[str, object]:
    tool_call = {
        "id": f"call_{uuid4().hex}",
        "type": "function",
        "function": {"name": TOOL_NAME, "arguments": arguments},
    }
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": None, "tool_calls": [tool_call]},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
