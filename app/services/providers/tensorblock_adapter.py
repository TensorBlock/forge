from typing import Any

from .azure_adapter import AzureAdapter

TENSORBLOCK_MODELS = [
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o-mini",
    "o3-mini",
    "text-embedding-3-large",
    "text-embedding-3-small",
    "text-embedding-ada-002",
]


class TensorblockAdapter(AzureAdapter):
    """Adapter for Tensorblock API"""

    def __init__(self, provider_name: str, base_url: str, config: dict[str, Any]):
        super().__init__(provider_name, base_url, config)

    def get_mapped_model(self, model: str) -> str:
        """Get the Azure-specific model name"""
        # For TensorBlock, we use the model name as-is since it's already in the correct format
        return model

    async def list_models(self, api_key: str) -> list[str]:
        return TENSORBLOCK_MODELS
