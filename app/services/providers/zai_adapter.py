from .openai_adapter import OpenAIAdapter

# https://docs.z.ai/api-reference/llm/chat-completion#body-model
ZAI_MODELS = [
    "glm-4.5",
    "glm-4.5-air",
    "glm-4.5-x",
    "glm-4.5-airx",
    "glm-4.5-flash",
    "glm-4-32b-0414-128k",
]


class ZAIAdapter(OpenAIAdapter):
    """Adapter for Zai API"""

    async def list_models(self, api_key: str) -> list[str]:
        return ZAI_MODELS