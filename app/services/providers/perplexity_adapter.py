from .openai_adapter import OpenAIAdapter

PERPLEXITY_MODELS = [
    "sonar",
    "sonar-reasoning-pro",
    "sonar-reasoning",
    "sonar-pro",
    "sonar",
    "sonar-deep-research",
]

class PerplexityAdapter(OpenAIAdapter):
    """Adapter for Perplexity API"""

    async def list_models(self, api_key: str) -> list[str]:
        return PERPLEXITY_MODELS
