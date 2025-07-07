import json
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar


class ProviderAdapter(ABC):
    """Base class for all provider adapters"""

    # Class-level cache for models across all adapter instances
    _models_cache: ClassVar[dict[str, list[str]]] = {}
    _models_cache_expiry: ClassVar[dict[str, float]] = {}
    _models_cache_ttl: ClassVar[int] = 3600  # 1 hour

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name"""
        pass

    @abstractmethod
    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
        base_url: str | None = None,
    ) -> Any:
        """Process a completion request"""
        pass

    @abstractmethod
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Process a embeddings request"""
        pass

    def get_cached_models(self, api_key: str, base_url: str | None) -> list[str] | None:
        """Get cached models if available and not expired"""
        cache_key = f"{self.provider_name}:{api_key}:{base_url or 'default'}"
        current_time = time.time()

        # Check if we have this key in cache and it's not expired
        if (
            cache_key in self._models_cache
            and self._models_cache_expiry.get(cache_key, 0) > current_time
        ):
            return self._models_cache[cache_key]
        return None
    
    @staticmethod
    def serialize_api_key_config(api_key: str, config: dict[str, Any] | None) -> str:
        """Serialize the API key for the given provider"""
        return api_key
    
    @staticmethod
    def deserialize_api_key_config(serialized_api_key_config: str) -> tuple[str, dict[str, Any] | None]:
        """Deserialize the API key for the given provider"""
        return serialized_api_key_config, None
    
    @staticmethod
    def mask_config(config: dict[str, Any]) -> dict[str, Any]:
        """Mask the config for the given provider"""
        return config

    def cache_models(
        self, api_key: str, base_url: str | None, models: list[str]
    ) -> None:
        """Cache models for this adapter"""
        cache_key = f"{self.provider_name}:{api_key}:{base_url or 'default'}"

        # Store the models in cache with expiry
        self._models_cache[cache_key] = models
        self._models_cache_expiry[cache_key] = time.time() + self._models_cache_ttl

    @abstractmethod
    async def list_models(self, api_key: str, base_url: str | None = None) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        pass
