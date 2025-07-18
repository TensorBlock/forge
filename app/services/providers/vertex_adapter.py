import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
import aiohttp
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from app.exceptions.exceptions import ProviderAuthenticationException, InvalidProviderConfigException, InvalidProviderAPIKeyException, ProviderAPIException

from app.core.async_cache import get_cached_oauth_token_async, cache_oauth_token_async, invalidate_oauth_token_cache_async
from app.core.logger import get_logger

from .base import ProviderAdapter
from .anthropic_adapter import AnthropicAdapter

logger = get_logger(name="vertex_adapter")


class VertexAdapter(ProviderAdapter):
    """Adapter for Vertex AI API"""

    def __init__(self, provider_name: str, base_url: str | None = None, config: dict[str, str] | None = None):
        self._provider_name = provider_name
        self._base_url = base_url.rstrip("/") if base_url else None
        self.config = config
        self.parse_config(config)

    @property
    def provider_name(self) -> str:
        return self._provider_name
    
    @staticmethod
    def validate_config(config: dict[str, str] | None):
        """Validate the config for the given provider"""
        try:
            assert config is not None
            assert config.get("publisher", "anthropic") is not None
            assert config.get("location") is not None
        except Exception as e:
            raise InvalidProviderConfigException("Vertex", e)
    
    def parse_config(self, config: dict[str, str] | None):
        """Validate the config for the given provider"""
        self.validate_config(config)
        self.publisher = config.get("publisher", "anthropic").lower()
        self.location = config["location"].lower()
    
    @staticmethod
    def validate_api_key(api_key: str):
        """Validate the API key for the given provider"""
        try:
            cred_json = json.loads(api_key)
            assert cred_json["type"] == "service_account"
            assert cred_json["project_id"] is not None
            assert cred_json["private_key_id"] is not None
            assert cred_json["private_key"] is not None
            assert cred_json["client_email"] is not None
            assert cred_json["client_id"] is not None
            assert cred_json["auth_uri"] is not None
            assert cred_json["token_uri"] is not None
            assert cred_json["auth_provider_x509_cert_url"] is not None
            assert cred_json["client_x509_cert_url"] is not None
            assert cred_json["universe_domain"] is not None

            return cred_json
        except Exception as e:
            raise InvalidProviderAPIKeyException("Vertex", e)
    
    def parse_api_key(self, api_key: str):
        """Validate the API key for the given provider"""
        try:
            cred_json = self.validate_api_key(api_key)
            self.project_id = cred_json["project_id"]
            self.cred_json = cred_json
        except Exception as e:
            raise ProviderAuthenticationException("Vertex", e)
    
    @staticmethod
    def serialize_api_key_config(api_key: str, config: dict[str, Any] | None) -> str:
        """Serialize the API key for the given provider"""
        VertexAdapter.validate_api_key(api_key)
        VertexAdapter.validate_config(config)
        return json.dumps({
            "api_key": api_key,
            "publisher": config.get("publisher", "anthropic"),
            "location": config["location"],
        })
    
    @staticmethod
    def deserialize_api_key_config(serialized_api_key_config: str) -> tuple[str, dict[str, Any] | None]:
        """Deserialize the API key for the given provider"""
        deserialized_api_key_config = json.loads(serialized_api_key_config)
        return deserialized_api_key_config["api_key"], {
            "publisher": deserialized_api_key_config["publisher"],
            "location": deserialized_api_key_config["location"],
        }
    
    @staticmethod
    def mask_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
        """Mask the config for the given provider"""
        VertexAdapter.validate_config(config)
        return {
            "publisher": config.get("publisher", "anthropic"),
            "location": config["location"],
        }
    
    @staticmethod
    def mask_api_key(api_key: str) -> str:
        """Mask the API key for the given provider"""
        cred_json = VertexAdapter.validate_api_key(api_key)
        return json.dumps({
            "type": cred_json["type"],
            "project_id": ProviderAdapter.mask_api_key(cred_json["project_id"]),
            "private_key_id": ProviderAdapter.mask_api_key(cred_json["private_key_id"]),
            "private_key": ProviderAdapter.mask_api_key(cred_json["private_key"]),
            "client_email": ProviderAdapter.mask_api_key(cred_json["client_email"]),
            "client_id": ProviderAdapter.mask_api_key(cred_json["client_id"]),
            "auth_uri": cred_json["auth_uri"],
            "token_uri": cred_json["token_uri"],
            "auth_provider_x509_cert_url": cred_json["auth_provider_x509_cert_url"],
            "client_x509_cert_url": ProviderAdapter.mask_api_key(cred_json["client_x509_cert_url"]),
            "universe_domain": cred_json["universe_domain"],
        })
    
    async def vertex_authentication(self, api_key: str) -> str:
        # validate api key
        self.parse_api_key(api_key)

        # check cache first for existing valid token
        cached_token = await get_cached_oauth_token_async(api_key)
        if cached_token:
            token_str = cached_token.get("token")
            expiry_str = cached_token.get("expiry")
            if token_str and expiry_str:
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                    # Make expiry timezone-aware if it's naive (Google credentials are UTC)
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if expiry > datetime.now(timezone.utc):
                        return token_str
                except (ValueError, TypeError):
                    # Invalid cached token, clear it and continue to refresh
                    await invalidate_oauth_token_cache_async(api_key)

        # load credentials within scope
        try:
            credentials = service_account.Credentials.from_service_account_info(self.cred_json, scopes=["https://www.googleapis.com/auth/cloud-platform"])

            # refresh token - run in thread pool to avoid blocking
            await asyncio.to_thread(credentials.refresh, Request())
            
            # cache the token with expiry information
            if credentials.token and credentials.expiry:
                token_data = {
                    "token": credentials.token,
                    "expiry": credentials.expiry.isoformat()
                }
                await cache_oauth_token_async(api_key, token_data)
                
            return credentials.token
        except Exception as e:
            logger.error(f"Error authenticating with Vertex API: {e}")
            raise ProviderAuthenticationException("Vertex", e)

    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Check cache first
        cached_models = self.get_cached_models(api_key, self._base_url)
        if cached_models is not None:
            return cached_models

        token = await self.vertex_authentication(api_key)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/v1beta1/publishers/{self.publisher}/models"
        models = []
        async with aiohttp.ClientSession() as session:
            next_page_token = "###initial"
            while next_page_token:
                params = {}
                if next_page_token and next_page_token != "###initial":
                    params["pageToken"] = next_page_token
                async with session.get(url, headers=headers, params=params) as response:
                    results = await response.json()
                    next_page_token = results.get("nextPageToken")
                    for m in results["publisherModels"]:
                        name = m["name"]
                        version_id = m["versionId"]
                        model_id = f"{name.split('/')[-1]}@{version_id}"
                        models.append(model_id)

        self.cache_models(api_key, self._base_url, models)
        return models

    async def process_completion(self, endpoint: str, payload: dict[str, Any], api_key: str) -> Any:
        token = await self.vertex_authentication(api_key)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        streaming = payload.get("stream", False)
        model_name = payload["model"]
        anthropic_payload = AnthropicAdapter.convert_openai_payload_to_anthropic(payload)

        # vertex specific payload
        anthropic_payload["anthropic_version"] = "vertex-2023-10-16"
        del anthropic_payload["model"]

        def error_handler(error_text: str, http_status: int):
            try:
                error_json = json.loads(error_text)
                error_message = error_json.get("error", {}).get("message", "Unknown error")
                error_code = error_json.get("error", {}).get("code", http_status)
                raise ProviderAPIException("Vertex", error_code, error_message)
            except Exception:
                raise ProviderAPIException("Vertex", http_status, error_text)

        if streaming:
            # https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.endpoints/streamRawPredict
            # vertex doesn't do actual streaming, it just returns a stream of json objects
            url = f"{self._base_url}/v1/projects/{self.project_id}/locations/{self.location}/publishers/{self.publisher}/models/{model_name}:streamRawPredict"
            async def custom_stream_response(url, headers, anthropic_payload, model_name):
                async def stream_response() -> AsyncGenerator[bytes, None]:
                    resp = await AnthropicAdapter.process_regular_response(url, headers, anthropic_payload, model_name, error_handler)
                    resp['object'] = 'chat.completion.chunk'
                    for choice in resp['choices']:
                        choice['delta'] = choice['message']
                        del choice['message']
                    yield f"data: {json.dumps(resp)}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                return stream_response()
            return await custom_stream_response(url, headers, anthropic_payload, model_name)
        else:
            url = f"{self._base_url}/v1/projects/{self.project_id}/locations/{self.location}/publishers/{self.publisher}/models/{model_name}:rawPredict"
            return await AnthropicAdapter.process_regular_response(url, headers, anthropic_payload, model_name, error_handler)
    
    async def process_embeddings(self, payload: dict[str, Any]) -> Any:
        """Process a embeddings request using Vertex API"""
        raise NotImplementedError("Embedding for Vertex is not supported")
