import time
from collections.abc import Callable

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelConnectionError,
    ModelHTTPError,
    ModelRateLimitError,
    ModelRequestTimeout,
    ModelServerError,
    ModelUnavailableError,
)
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from email_agent.config import Settings, read_secret

LLM_KEY_SECRET = "llm_api_key"
OUTPUT_RETRIES = 2
BACKOFF_SECONDS = (2, 4, 8)
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500


class LlmConfigError(Exception):
    pass


def build_model(settings: Settings) -> Model:
    """
    @example
    build_model(settings)  # LLM_MODEL=openai:sonnet → OpenAIChatModel("sonnet")
    """
    provider, _, model_name = settings.llm_model.partition(":")
    if not model_name:
        raise LlmConfigError(f"Invalid setting LLM_MODEL: expected provider:model, got {settings.llm_model}")
    try:
        api_key = read_secret(settings, LLM_KEY_SECRET)
    except OSError:
        raise LlmConfigError(f"LLM key missing: {settings.secrets_dir / LLM_KEY_SECRET}") from None
    match provider:
        case "anthropic":
            client = AsyncAnthropic(api_key=api_key, base_url=settings.llm_base_url, max_retries=0)
            return AnthropicModel(model_name, provider=AnthropicProvider(anthropic_client=client))
        case "openai":
            client = AsyncOpenAI(api_key=api_key, base_url=settings.llm_base_url, max_retries=0)
            return OpenAIChatModel(model_name, provider=OpenAIProvider(openai_client=client))
        case _:
            raise LlmConfigError(f"Invalid setting LLM_MODEL: unknown provider {provider}")


def is_transient(error: AgentRunError) -> bool:
    if isinstance(error, ModelHTTPError):
        return error.status_code == HTTP_TOO_MANY_REQUESTS or error.status_code >= HTTP_SERVER_ERROR
    return isinstance(
        error,
        (
            ModelConnectionError,
            ModelRequestTimeout,
            ModelRateLimitError,
            ModelServerError,
            ModelUnavailableError,
        ),
    )


def call_with_backoff[T](call: Callable[[], T]) -> T:
    """
    @example
    call_with_backoff(lambda: agent.run_sync(prompt).output)
    # wrapper down → waits 2, 4, 8 s, then raises the last ModelConnectionError
    """
    for wait_seconds in BACKOFF_SECONDS:
        try:
            return call()
        except AgentRunError as error:
            if not is_transient(error):
                raise
            print(f"LLM request failed, retrying in {wait_seconds} s: {error}")
            time.sleep(wait_seconds)
    return call()
