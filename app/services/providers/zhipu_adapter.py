from .openai_adapter import OpenAIAdapter
ZHIPU_MODELS = [
    "glm-4-plus",
    "glm-4-0520",
    "glm-4",
    "glm-4-air",
    "glm-4-airx",
    "glm-4-long",
    "glm-4-flash",
    "glm-4v-plus-0111",
    "glm-4v-flash"
    "glm-z1-air",
    "glm-z1-airx",
    "glm-z1-flash",
]

class ZhipuAdapter(OpenAIAdapter):
    """Adapter for Zhipu API"""

    async def list_models(self, api_key: str) -> list[str]:
        return ZHIPU_MODELS
