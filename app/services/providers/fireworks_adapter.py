from .openai_adapter import OpenAIAdapter
from typing import Any


class FireworksAdapter(OpenAIAdapter):
    """Adapter for Fireworks API"""

    FIREWORKS_MODEL_MAPPING = {
        "Llama 4 Maverick Instruct (Basic)": "accounts/fireworks/models/llama4-maverick-instruct-basic",
        "Llama 4 Scout Instruct (Basic)": "accounts/fireworks/models/llama4-scout-instruct-basic",
        "Llama 3.1 405B Instruct": "accounts/fireworks/models/llama-v3p1-405b-instruct",
        "Llama 3.1 8B Instruct": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "Llama 3.3 70B Instruct": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "Llama 3.2 90B Vision Instruct": "accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
        "DeepSeek V3": "accounts/fireworks/models/deepseek-v3",
        "DeepSeek R1 (Fast)": "accounts/fireworks/models/deepseek-r1",
        "DeepSeek R1 (Basic)": "accounts/fireworks/models/deepseek-r1-basic",
        "Deepseek V3 03-24": "accounts/fireworks/models/deepseek-v3-0324",
        "Qwen Qwq 32b Preview": "accounts/fireworks/models/qwen-qwq-32b-preview",
        "Phi 3.5 Vision Instruct": "accounts/fireworks/models/phi-3-vision-128k-instruct",
        "Firesearch Ocr V6": "accounts/fireworks/models/firesearch-ocr-v6",
        "Yi-Large": "accounts/yi-01-ai/models/yi-large",
        "Llama V3p1 405b Instruct Long": "accounts/fireworks/models/llama-v3p1-405b-instruct-long",
        "Llama Guard 3 8b": "accounts/fireworks/models/llama-guard-3-8b",
        "Dobby-Unhinged-Llama-3.3-70B": "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new",
        "Mixtral MoE 8x22B Instruct": "accounts/fireworks/models/mixtral-8x22b-instruct",
        "Qwen2.5 72B Instruct": "accounts/fireworks/models/qwen2p5-72b-instruct",
        "QwQ-32B": "accounts/fireworks/models/qwq-32b",
        "Qwen2 VL 72B Instruct": "accounts/fireworks/models/qwen2-vl-72b-instruct",
    }

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        config: dict[str, Any] | None = None,
    ):
        self._base_url = base_url
        super().__init__(provider_name, base_url, config=config)

    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Check cache first
        cached_models = self.get_cached_models(api_key, self._base_url)
        if cached_models is not None:
            return cached_models

        # If not in cache, make API call
        # headers = {
        #     "Authorization": f"Bearer {api_key}",
        #     "Content-Type": "application/json",
        # }
        # fireworks models requires a account id, which we use the official account fireworks
        # https://docs.fireworks.ai/api-reference/list-models
        # And fireworks inference api and list models api doesn't share the same base url
        # url = "https://api.fireworks.ai/v1/accounts/fireworks/models"

        # async with (
        #     aiohttp.ClientSession() as session,
        #     session.get(url, headers=headers, params={"pageSize": 200}) as response,
        # ):
        #     if response.status != HTTPStatus.OK:
        #         error_text = await response.text()
        #         raise ValueError(f"Fireworks API error: {error_text}")
        #     resp = await response.json()
        #     self.FIREWORKS_MODEL_MAPPING = {
        #         d["displayName"]: d["name"] for d in resp["models"]
        #     }
        #     return [d["name"] for d in resp["models"]]

        # TODO: currently fireworks api doesn't support list all the serverless models
        # We simply hardcode the models here
        return list(self.FIREWORKS_MODEL_MAPPING.values())
