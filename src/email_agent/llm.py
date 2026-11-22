from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from email_agent.config import Settings, read_secret

LLM_KEY_SECRET = "llm_api_key"


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
            return AnthropicModel(
                model_name, provider=AnthropicProvider(api_key=api_key, base_url=settings.llm_base_url)
            )
        case "openai":
            return OpenAIChatModel(
                model_name, provider=OpenAIProvider(base_url=settings.llm_base_url, api_key=api_key)
            )
        case _:
            raise LlmConfigError(f"Invalid setting LLM_MODEL: unknown provider {provider}")
