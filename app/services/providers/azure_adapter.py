import json
from typing import Any

from .openai_adapter import OpenAIAdapter
from app.core.logger import get_logger
from app.exceptions.exceptions import ProviderAPIException, BaseInvalidProviderSetupException

# Configure logging
logger = get_logger(name="azure_adapter")

class AzureAdapter(OpenAIAdapter):
    def __init__(self, provider_name: str, base_url: str, config: dict[str, Any]):
        self.api_version = config.get("api_version", "2025-01-01-preview")
        self._base_url = AzureAdapter.assert_valid_base_url(base_url)
        super().__init__(provider_name, self._base_url, config=config)

    @staticmethod
    def assert_valid_base_url(base_url: str) -> str:
        # base_url is required
        # e.g: https://THE-RESOURCE-NAME.openai.azure.com/
        if not base_url:
            error_text = "Azure base URL is required"
            logger.error(error_text)
            raise BaseInvalidProviderSetupException(
                provider_name="azure",
                error=ValueError(error_text)
            )
        base_url = base_url.rstrip("/")
        return base_url
    
    @staticmethod
    def serialize_api_key_config(api_key: str, config: dict[str, Any] | None) -> str:
        """Serialize the API key for the given provider"""
        try:
            assert config is not None
            assert config.get("api_version") is not None
        except AssertionError as e:
            logger.error(str(e))
            raise BaseInvalidProviderSetupException(
                provider_name="azure",
                error=e
            )

        return json.dumps({
            "api_key": api_key,
            "api_version": config["api_version"],
        })
    
    @staticmethod
    def deserialize_api_key_config(serialized_api_key_config: str) -> tuple[str, dict[str, Any] | None]:
        """Deserialize the API key for the given provider"""
        try:
            deserialized_api_key_config = json.loads(serialized_api_key_config)
            assert deserialized_api_key_config.get("api_key") is not None
            assert deserialized_api_key_config.get("api_version") is not None
        except Exception as e:
            logger.error(str(e))
            raise BaseInvalidProviderSetupException(
                provider_name="azure",
                error=e
            )

        return deserialized_api_key_config["api_key"], {
            "api_version": deserialized_api_key_config["api_version"],
        }
    
    @staticmethod
    def process_streaming_chunk(chunk: bytes):
        """
        For some reason, Azure API returns a chunk which includes an empty choices array.
        We need to add a default choice to the chunk.
        """
        chunk_str = chunk.decode("utf-8")
        if chunk_str.startswith("data:"):
            chunk_str = chunk_str[len("data:"):]
        else:
            return chunk
        chunk_str = chunk_str.strip()
        if chunk_str:
            try:
                chunk_json = json.loads(chunk_str)
                if not chunk_json.get("choices"):
                    chunk_json["choices"] =  [{
                        "index": 0,
                        "delta": {},
                    }]
                    return f'data: {json.dumps(chunk_json)}\n\n'.encode("utf-8")
                return chunk
            except json.JSONDecodeError:
                return chunk
        return chunk

    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process a completion request using Azure API"""
        # Azure API requires the model to be in the path
        model_id = payload["model"]
        del payload["model"]
        base_url = f"{self._base_url}/openai/deployments/{model_id}"

        query_params = {
            "api-version": self.api_version,
        }
        return await super().process_completion(endpoint, payload, api_key, base_url, query_params)
    
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process an embeddings request using Azure API"""
        # Azure API requires the model to be in the path
        model_id = payload["model"]
        del payload["model"]
        base_url = f"{self._base_url}/openai/deployments/{model_id}"

        query_params = {
            "api-version": self.api_version,
        }
        return await super().process_embeddings(endpoint, payload, api_key, base_url, query_params)
    
    async def list_models(self, api_key: str) -> list[str]:
        base_url = f"{self._base_url}/openai"
        query_params = {
            "api-version": self.api_version,
        }
        return await super().list_models(api_key, base_url, query_params)