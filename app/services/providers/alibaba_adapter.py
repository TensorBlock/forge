from .openai_adapter import OpenAIAdapter

ALIBABA_MODELS = [
    "qwen-max",
    "qwen-max-latest",
    "qwen-max-2025-01-25",
    "qwen-plus",
    "qwen-plus-latest",
    "qwen-plus-2025-04-28",
    "qwen-plus-2025-01-25",
    "qwen-turbo",
    "qwen-turbo-latest",
    "qwen-turbo-2025-04-28",
    "qwen-turbo-2024-11-01",
    "qwq-32b",
    "qwen3-235b-a22b",
    "qwen3-32b",
    "qwen3-30b-a3b",
    "qwen3-14b",
    "qwen3-8b",
    "qwen3-4b",
    "qwen3-1.7b",
    "qwen3-0.6b",
    "qwen2.5-14b-instruct-1m",
    "qwen2.5-7b-instruct-1m",
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct",
    "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct",
    "qwen2-72b-instruct",
    "qwen2-7b-instruct",
    "qwen1.5-110b-chat",
    "qwen1.5-72b-chat",
    "qwen1.5-32b-chat",
    "qwen1.5-14b-chat",
    "qwen1.5-7b-chat",
]

class AlibabaAdapter(OpenAIAdapter):
    """Adapter for Alibaba API"""

    async def list_models(self, api_key: str) -> list[str]:
        return ALIBABA_MODELS