from typing import Any

from app.core.logger import get_logger
from .openai_adapter import OpenAIAdapter

# Configure logging
logger = get_logger(name="gemini_openai_adapter")


class GeminiOpenAIAdapter(OpenAIAdapter):
    """Adapter for Google Gemini via the OpenAI-compatible endpoint

    Google now exposes Gemini models behind an OpenAI-compatible REST surface at
    https://generativelanguage.googleapis.com/v1beta/openai/…

    We can therefore reuse all logic in OpenAIAdapter.  The only wrinkle is that
    callers might supply the base_url without the trailing `/openai` segment,
    so we normalise it here.
    """

    def __init__(
        self,
        provider_name: str,
        base_url: str | None,
        config: dict[str, Any] | None = None,
    ):
        # Default base URL if none supplied
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"

        # Ensure the URL ends with the OpenAI compatibility suffix
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/openai"):
            base_url = f"{base_url}/openai"

        logger.debug(f"Initialised GeminiOpenAIAdapter with base_url={base_url}")

        super().__init__(provider_name, base_url, config=config or {}) 