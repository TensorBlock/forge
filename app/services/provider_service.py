import asyncio
import uuid
import inspect
import json
import os
import time
from collections.abc import AsyncGenerator
from typing import Any, ClassVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_cache import async_provider_service_cache, DEBUG_CACHE
from app.core.logger import get_logger
from app.core.security import decrypt_api_key, encrypt_api_key
from app.exceptions.exceptions import (
    InvalidProviderException,
    BaseInvalidRequestException,
    InvalidForgeKeyException,
)
from app.models.user import User
from app.models.provider_key import ProviderKey
from app.core.database import get_db_session
from app.services.wallet_service import WalletService

from .providers.adapter_factory import ProviderAdapterFactory
from .providers.base import ProviderAdapter
from .providers.usage_tracker_service import UsageTrackerService

logger = get_logger(name="provider_service")

# Add constants at the top of the file, after imports
MODEL_PARTS_MIN_LENGTH = 2  # Minimum number of parts in a model name (e.g., "gpt-4")


# Create a background task to update the usage tracker that won't be cancelled
# Even if the streaming response is cancelled by client disconnect
async def update_usage_in_background(
    usage_tracker_id: uuid.UUID,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    reasoning_tokens: int,
):
    # Use a fresh DB session for logging, since the original request session
    # may have been closed by FastAPI after the response was returned.

    async with get_db_session() as new_db_session:
        await UsageTrackerService.update_usage_tracker(
            db=new_db_session,
            usage_tracker_id=usage_tracker_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )


class ProviderService:
    """Service for handling provider API calls.

    This class implements a multi-level caching strategy:
    1. Instance caching: Each user gets one cached ProviderService instance (use get_instance method)
    2. Provider keys caching: API keys are cached for 1 hour to reduce database queries
    3. Models caching: Available models are cached for 1 hour to reduce API calls

    To ensure you're using the cached instance, always create instances via the get_instance()
    class method rather than direct instantiation.
    """

    # Class-level cache for adapters to avoid recreating them
    _adapters_cache: ClassVar[dict[str, ProviderAdapter]] = {}

    # TTL for model lists in both Redis (L2) and in-process dict (L1)
    _models_cache_ttl: ClassVar[int] = int(
        os.getenv("MODELS_CACHE_TTL", "300")
    )  # default 5 minutes

    # In-process (L1) cache: key -> (expiry_ts, models_list)
    _models_l1_cache: ClassVar[dict[str, tuple[float, list[dict[str, Any]]]]] = {}

    # ------------------------------------------------------------------
    # Helper for building a cache key that works across all workers.
    # Stored via app.core.async_cache.async_provider_service_cache which resolves to
    # either RedisCache or in-memory Cache.
    # ------------------------------------------------------------------

    @classmethod
    def _model_cache_key(cls, provider_name: str, cache_key: str) -> str:
        # Using a stable namespace makes invalidation easier
        return f"models:{provider_name}:{cache_key}"

    def __init__(self, user_id: int, db: AsyncSession, api_key_id: int | None = None):
        self.user_id = user_id
        self.db = db
        self.api_key_id = api_key_id
        self.provider_keys: dict[str, dict[str, Any]] = {}
        self.adapters = self._get_adapters()
        # Load provider keys on demand, not during initialization
        self._keys_loaded = False

    @classmethod
    async def async_get_instance(
        cls, user: User, db: AsyncSession, api_key_id: int | None = None
    ) -> "ProviderService":
        """Get a cached instance of ProviderService for a user or create a new one (async version)"""

        cache_key = f"provider_service:{user.id}"
        cached_instance = await async_provider_service_cache.get(cache_key)
        if cached_instance:
            if DEBUG_CACHE:
                logger.debug(
                    f"Using cached ProviderService instance for user {user.id} (async)"
                )
            # Update the db session reference for the cached instance
            cached_instance.db = db
            cached_instance.api_key_id = api_key_id
            return cached_instance

        # No cached instance found, create a new one (async)
        if DEBUG_CACHE:
            logger.debug(
                f"Creating new ProviderService instance for user {user.id} (async)"
            )
        instance = cls(user.id, db, api_key_id)
        await async_provider_service_cache.set(cache_key, instance)
        return instance

    @classmethod
    async def get_cached_models(
        cls, provider_name: str, cache_key: str
    ) -> list[dict[str, Any]] | None:
        """Return cached model list if present (shared cache)."""
        key = cls._model_cache_key(provider_name, cache_key)

        # -------- L1: in-process dict --------
        l1_entry = cls._models_l1_cache.get(key)
        if l1_entry and time.time() < l1_entry[0]:
            if DEBUG_CACHE:
                logger.debug(f"L1 model cache HIT for provider {provider_name}")
            return l1_entry[1]

        # -------- L2: shared cache (Redis / memory) --------
        models = await async_provider_service_cache.get(key)
        if models:
            # populate L1
            cls._models_l1_cache[key] = (time.time() + cls._models_cache_ttl, models)
            if DEBUG_CACHE:
                logger.debug(f"L2 model cache HIT for provider {provider_name}")
        return models

    @classmethod
    async def cache_models(
        cls, provider_name: str, cache_key: str, models: list[dict[str, Any]]
    ) -> None:
        """Store models in the shared cache with a TTL."""
        key = cls._model_cache_key(provider_name, cache_key)

        # Write to shared cache (L2)
        await async_provider_service_cache.set(key, models, ttl=cls._models_cache_ttl)

        # Populate/refresh L1
        cls._models_l1_cache[key] = (time.time() + cls._models_cache_ttl, models)

        if DEBUG_CACHE:
            logger.debug(
                f"Cached models for provider {provider_name} (TTL: {cls._models_cache_ttl}s)"
            )

    def _get_adapters(self) -> dict[str, ProviderAdapter]:
        """Get adapters from cache or create new ones"""
        if not ProviderService._adapters_cache:
            ProviderService._adapters_cache = ProviderAdapterFactory.get_all_adapters()
        return ProviderService._adapters_cache

    async def _load_provider_keys(self) -> dict[str, dict[str, Any]]:
        """Load all provider keys for the user synchronously, with lazy loading and caching."""
        if self._keys_loaded:
            return self.provider_keys

        # Try to get provider keys from cache
        cache_key = f"provider_keys:{self.user_id}"
        cached_keys = await async_provider_service_cache.get(cache_key)
        if cached_keys is not None:
            if DEBUG_CACHE:
                logger.debug(
                    f"Using cached provider keys for user {self.user_id} (sync)"
                )
            self.provider_keys = cached_keys
            self._keys_loaded = True
            return self.provider_keys

        if DEBUG_CACHE:
            logger.debug(
                f"Loading provider keys from database for user {self.user_id} (sync)"
            )

        result = await self.db.execute(
            select(ProviderKey).filter(
                ProviderKey.user_id == self.user_id, ProviderKey.deleted_at == None
            )
        )
        provider_key_records = result.scalars().all()

        keys = {}
        for provider_key in provider_key_records:
            model_mapping = provider_key.model_mapping or {}

            # Normalize provider name to lowercase for consistent lookup
            normalized_provider_name = provider_key.provider_name.lower()

            keys[normalized_provider_name] = {
                "id": provider_key.id,
                "api_key": decrypt_api_key(provider_key.encrypted_api_key),
                "base_url": provider_key.base_url,
                "model_mapping": model_mapping,
            }

        self.provider_keys = keys
        self._keys_loaded = True

        # Cache the provider keys
        if DEBUG_CACHE:
            logger.debug(
                f"Caching provider keys for user {self.user_id} (TTL: 3600s) (sync)"
            )
        await async_provider_service_cache.set(
            cache_key, keys, ttl=3600
        )  # Cache for 1 hour

        return keys

    async def _load_provider_keys_async(self) -> dict[str, dict[str, Any]]:
        """Load all provider keys for the user asynchronously, with lazy loading and caching."""
        if self._keys_loaded:
            return self.provider_keys

        # Try to get provider keys from cache
        cache_key = f"provider_keys:{self.user_id}"
        cached_keys = await async_provider_service_cache.get(cache_key)
        if cached_keys is not None:
            if DEBUG_CACHE:
                logger.debug(
                    f"Using cached provider keys for user {self.user_id} (async)"
                )
            self.provider_keys = cached_keys
            self._keys_loaded = True
            return self.provider_keys

        if DEBUG_CACHE:
            logger.debug(
                f"Loading provider keys from database for user {self.user_id} (async)"
            )

        result = await self.db.execute(
            select(ProviderKey).filter(
                ProviderKey.user_id == self.user_id, ProviderKey.deleted_at == None
            )
        )
        provider_key_records = result.scalars().all()

        keys = {}
        for provider_key in provider_key_records:
            model_mapping = provider_key.model_mapping or {}

            # Normalize provider name to lowercase for consistent lookup
            normalized_provider_name = provider_key.provider_name.lower()

            keys[normalized_provider_name] = {
                "id": provider_key.id,
                "api_key": decrypt_api_key(provider_key.encrypted_api_key),
                "base_url": provider_key.base_url,
                "model_mapping": model_mapping,
            }

        self.provider_keys = keys
        self._keys_loaded = True

        # Cache the provider keys
        if DEBUG_CACHE:
            logger.debug(
                f"Caching provider keys for user {self.user_id} (TTL: 3600s) (async)"
            )
        await async_provider_service_cache.set(
            cache_key, keys, ttl=3600
        )  # Cache for 1 hour

        return keys

    def _extract_provider_name_prefix(
        self, model: str, allowed_provider_names: list[str] | set[str] | None = None
    ) -> tuple[str | None, str]:
        """
        Extracts a provider name prefix from the model name if it exists.
        Returns (provider_prefix, model_name_without_prefix)

        Args:
            model: The model name to extract provider prefix from
            allowed_provider_names: Optional list/set of allowed provider names for security scope.
                                   If provided, only checks against these providers (which are already
                                   the intersection of user's provider keys and API key scope).
                                   If None, checks against user's provider keys.
        """
        # Determine which provider names to check against
        if not self._keys_loaded:
            return None, model

        # Get user's available provider names (already normalized to lowercase)
        user_provider_names = set(self.provider_keys.keys())

        if allowed_provider_names:
            # allowed_provider_names is already the intersection of user's provider keys and API key scope
            # (determined by the forge_api_key_provider_scope_association table)
            allowed_providers_lower = {p.lower() for p in allowed_provider_names}

            # Use the optimized approach with allowed providers
            model_lower = model.lower()

            # Sort providers by length (longest first) to avoid substring conflicts
            # e.g., "openai-custom" should match before "openai"
            sorted_providers = sorted(allowed_providers_lower, key=len, reverse=True)

            for provider in sorted_providers:
                # Check if provider is at the start of the model string
                if model_lower.startswith(provider + "/"):
                    # Find the original case from allowed_provider_names
                    original_provider = next(
                        p for p in allowed_provider_names if p.lower() == provider
                    )

                    # Extract the model name without prefix
                    prefix_length = len(provider) + 1  # +1 for the "/"
                    model_name_without_prefix = model[prefix_length:]

                    # Return the provider name in lowercase to match the provider keys
                    return original_provider.lower(), model_name_without_prefix
        else:
            # Use the comprehensive approach checking user's provider keys
            all_provider_names = user_provider_names

            model_parts = model.split("/")

            # Find the longest matching provider name from the start of the model string
            for i in range(len(model_parts), 0, -1):
                potential_provider = "/".join(model_parts[:i]).lower()
                if potential_provider in all_provider_names:
                    # If the provider name is the entire model string, and it has only one part,
                    # then we should treat it as a model name, not a provider prefix.
                    # e.g. model name is "openai", we shouldn't parse it as provider "openai" and empty model.
                    is_entire_model_string = i == len(model_parts)
                    if is_entire_model_string and len(model_parts) == 1:
                        continue  # Skip, treat as model name

                    provider_name = potential_provider
                    model_name_without_prefix = "/".join(model_parts[i:])
                    return provider_name, model_name_without_prefix

        return None, model

    def _get_provider_info_with_prefix(
        self, provider_name: str, model_name: str, original_model: str
    ) -> tuple[str, str, str | None, int | None]:
        """Handles provider lookup when a prefix is found in the model name."""
        # Provider keys are now normalized to lowercase, so we can do direct lookup
        provider_name_lower = provider_name.lower()
        matching_provider = next(
            (key for key in self.provider_keys.keys() if key == provider_name_lower),
            None,
        )

        if not matching_provider:
            logger.error(f"No matching provider found for {original_model}")
            raise InvalidProviderException(original_model)

        provider_data = self.provider_keys[matching_provider]

        model_mapping = provider_data.get("model_mapping", {})
        provider_key_id = provider_data.get("id")
        mapped_model = model_mapping.get(model_name, model_name)
        return (
            matching_provider,
            mapped_model,
            provider_data.get("base_url"),
            provider_key_id,
        )

    def _find_provider_for_unprefixed_model(
        self, model: str
    ) -> tuple[str, str, str | None, int | None]:
        """Finds a provider for a model that doesn't have a provider prefix."""
        # Prioritize providers whose names are substrings of the model, e.g., "gemini" in "models/gemini-2.0-flash"
        # This helps resolve ambiguity when multiple providers might claim to support a model.
        # Create a sorted list of providers, prioritizing those with names in the model string.
        sorted_providers = sorted(
            self.provider_keys.items(),
            key=lambda item: item[0] in model,
            reverse=True,
        )

        # Check custom model mappings
        for provider_name, provider_data in sorted_providers:
            model_mapping = provider_data.get("model_mapping", {})
            provider_key_id = provider_data.get("id")
            if model in model_mapping:
                mapped_model = model_mapping[model]
                return (
                    provider_name,
                    mapped_model,
                    provider_data.get("base_url"),
                    provider_key_id,
                )

        logger.error(f"No matching provider found for {model}")
        raise InvalidProviderException(model)

    def _get_provider_info(
        self, model: str, allowed_provider_names: list[str] | set[str] | None = None
    ) -> tuple[str, str, str | None, int | None]:
        """
        Determine the provider based on the model name.
        If allowed_provider_names is provided, use optimized lookup for faster performance.
        """
        if not self._keys_loaded:
            error_message = "Provider keys must be loaded before calling _get_provider_info. Call _load_provider_keys_async() first."
            logger.error(error_message)
            raise RuntimeError(error_message)

        # Use the unified provider name extraction method
        provider_name, model_name_no_prefix = self._extract_provider_name_prefix(
            model, allowed_provider_names
        )

        if provider_name:
            return self._get_provider_info_with_prefix(
                provider_name, model_name_no_prefix, model
            )

        return self._find_provider_for_unprefixed_model(model)

    async def list_models(
        self, allowed_provider_names: list[str] | set[str] | None = None
    ) -> list[dict[str, Any]]:
        logger.info(
            f"Listing models for allowed_provider_names: {allowed_provider_names}"
        )
        """List all models supported by the provider, with caching to avoid repeated API calls
        Optionally limit the list to providers included in `allowed_provider_names`."""
        # Ensure provider keys are loaded
        if not self._keys_loaded:
            await self._load_provider_keys_async()

        models = []
        tasks = []

        # Determine which providers are allowed (case-insensitive).
        #   allowed_provider_names is:
        #       • None -> no restriction (all providers)
        #       • []   -> explicitly no providers allowed (empty set)
        #       • list -> restrict to that set
        if allowed_provider_names is None:
            allowed_set = None  # unrestricted
        else:
            allowed_set = {name.lower() for name in allowed_provider_names}

        for provider_name, provider_data in self.provider_keys.items():
            if allowed_set is not None and provider_name.lower() not in allowed_set:
                continue

            # Create a cache key unique to this provider config
            base_url = provider_data.get("base_url", "default")
            cache_key = f"{base_url}:{hash(frozenset(provider_data.get('model_mapping', {}).items()))}"

            # Check if we have cached models for this provider
            cached_models = await self.get_cached_models(provider_name, cache_key)
            if cached_models:
                models.extend(cached_models)
                continue

            # If not cached, fetch the models
            async def _list_models_helper(
                adapter: ProviderAdapter,
                api_key: str,
                provider_data: dict[str, Any],
                provider_name=provider_name,
                cache_key=cache_key,
            ) -> list[dict[str, Any]]:
                try:
                    model_names = await adapter.list_models(api_key)
                    model_mapping = provider_data.get("model_mapping", {})
                    reverse_model_mapping = {v: k for k, v in model_mapping.items()}
                    provider_models = [
                        {
                            "id": f"{provider_name}/{model}",
                            "display_name": reverse_model_mapping.get(model, model),
                            "object": "model",
                            "owned_by": provider_name,
                        }
                        for model in model_names
                    ]
                    # Cache the results
                    await self.cache_models(provider_name, cache_key, provider_models)

                    return provider_models
                except Exception as e:
                    # Use parameterized logging to avoid issues if the error message contains braces
                    logger.error(
                        "Error fetching models for {}: {}", provider_name, str(e)
                    )
                    return []

            provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(provider_name)
            serialized_api_key_config = self.provider_keys[provider_name]["api_key"]
            api_key, config = provider_adapter_cls.deserialize_api_key_config(
                serialized_api_key_config
            )
            base_url = self.provider_keys[provider_name]["base_url"]
            tasks.append(
                _list_models_helper(
                    ProviderAdapterFactory.get_adapter(provider_name, base_url, config),
                    api_key,
                    provider_data,
                )
            )

        # Process model listing tasks in batches to avoid overwhelming APIs
        concurrent_tasks_size = 5
        for i in range(0, len(tasks), concurrent_tasks_size):
            results = await asyncio.gather(*tasks[i : i + concurrent_tasks_size])
            for result in results:
                models.extend(result)

        return models

    async def process_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        allowed_provider_names: list[str] | set[str] | None = None,
    ) -> Any:
        """Process an API request, routing it to the appropriate provider."""

        # Ensure provider keys are loaded
        if not self._keys_loaded:
            await self._load_provider_keys_async()

        model = payload.get("model")
        if not model:
            error_message = "Model is required"
            logger.error(error_message)
            raise BaseInvalidRequestException(
                provider_name="unknown", error=ValueError(error_message)
            )

        provider_name, actual_model, base_url, provider_key_id = (
            self._get_provider_info(model, allowed_provider_names)
        )

        # Enforce scope restriction (case-insensitive).
        if allowed_provider_names is not None and (
            provider_name.lower() not in {p.lower() for p in allowed_provider_names}
        ):
            error_message = (
                f"API key is not permitted to use provider '{provider_name}'."
            )
            logger.error(error_message)
            raise InvalidForgeKeyException(error=ValueError(error_message))

        logger.debug(
            f"Processing request for provider: {provider_name}, model: {actual_model}, endpoint: {endpoint}"
        )

        # Update the model name if mapped
        payload["model"] = actual_model

        # Get the provider's API key
        if provider_name not in self.provider_keys:
            error_message = (
                f"API key is not permitted to use provider '{provider_name}'."
            )
            logger.error(error_message)
            raise InvalidForgeKeyException(error=ValueError(error_message))

        serialized_api_key_config = self.provider_keys[provider_name]["api_key"]
        provider_adapter_cls = ProviderAdapterFactory.get_adapter_cls(provider_name)
        api_key, config = provider_adapter_cls.deserialize_api_key_config(
            serialized_api_key_config
        )

        # Get the appropriate adapter
        adapter = ProviderAdapterFactory.get_adapter(provider_name, base_url, config)

        # Process the request through the adapter
        usage_tracker_id = None
        if self.api_key_id is not None and provider_key_id is not None:
            result = await self.db.execute(select(ProviderKey.billable).where(ProviderKey.id == provider_key_id))
            billable = result.scalar_one_or_none() or False
            if billable:
                await WalletService.wallet_precheck(self.user_id, self.db)
            usage_tracker_id = await UsageTrackerService.start_tracking_usage(
                db=self.db,
                user_id=self.user_id,
                provider_key_id=provider_key_id,
                forge_key_id=self.api_key_id,
                model=actual_model,
                endpoint=endpoint,
                billable=billable,
            )
        else:
            # For api like list models, we don't have usage tracking
            logger.info(
                f"api_key_id: {self.api_key_id}, provider_key_id: {provider_key_id}"
            )
            logger.warning(
                "No API key ID or provider key ID found, skipping usage tracking"
            )

        if "completion" in endpoint:
            result = await adapter.process_completion(
                endpoint,
                payload,
                api_key,
            )
        elif "images/generations" in endpoint:
            # TODO: we only support openai for now
            if provider_name != "openai":
                error_message = (
                    f"Unsupported endpoint: {endpoint} for provider {provider_name}"
                )
                logger.error(error_message)
                raise NotImplementedError(error_message)
            result = await adapter.process_image_generation(
                endpoint,
                payload,
                api_key,
            )
        elif "images/edits" in endpoint:
            # TODO: we only support openai for now
            if provider_name != "openai":
                error_message = (
                    f"Unsupported endpoint: {endpoint} for provider {provider_name}"
                )
                logger.error(error_message)
                raise NotImplementedError(error_message)
            result = await adapter.process_image_edits(
                endpoint,
                payload,
                api_key,
            )
        elif "embeddings" in endpoint:
            result = await adapter.process_embeddings(
                endpoint,
                payload,
                api_key,
            )
        else:
            error_message = f"Unsupported endpoint: {endpoint}"
            logger.error(error_message)
            # Delete the usage tracker record if it exists
            await UsageTrackerService.delete_usage_tracker_record(
                db=self.db,
                usage_tracker_id=usage_tracker_id,
            )
            raise NotImplementedError(error_message)

        # Track usage statistics if it's not a streaming response
        if not inspect.isasyncgen(result):
            # Extract usage data from the response
            input_tokens = 0
            output_tokens = 0
            cached_tokens = 0
            reasoning_tokens = 0

            # https://platform.openai.com/docs/api-reference/chat/object#chat/object-usage
            if isinstance(result, dict) and "usage" in result:
                usage = result.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0) or input_tokens
                output_tokens = usage.get("completion_tokens", 0) or output_tokens
                total_tokens = usage.get("total_tokens", 0) or (input_tokens + output_tokens)
                prompt_tokens_details = usage.get("prompt_tokens_details", {}) or {}
                completion_tokens_details = usage.get("completion_tokens_details", {}) or {}
                cached_tokens = prompt_tokens_details.get("cached_tokens", 0)
                reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0) or (total_tokens - input_tokens - output_tokens)

                # re-calculate output tokens
                output_tokens = max(output_tokens, total_tokens - input_tokens)

            asyncio.create_task(
                update_usage_in_background(
                    usage_tracker_id,
                    input_tokens,
                    output_tokens,
                    cached_tokens,
                    reasoning_tokens,
                )
            )
            return result
        else:
            # For streaming responses, wrap the generator to count tokens
            async def token_counting_stream() -> AsyncGenerator[bytes, None]:
                approximate_input_tokens = 0
                approximate_output_tokens = 0
                output_tokens = 0
                input_tokens = 0
                total_tokens = 0
                cached_tokens = 0
                reasoning_tokens = 0
                chunks_processed = 0

                # Get the streaming mode from the payload
                stream_mode = payload.get("stream", False)
                logger.debug(
                    f"Streaming mode: {stream_mode} for {provider_name} request"
                )

                messages = payload.get("messages", [])

                # Rough estimate of input tokens based on message length
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        # Rough approximation: 4 chars ~= 1 token
                        approximate_input_tokens += len(content) // 4

                try:
                    async for chunk in result:
                        chunks_processed += 1

                        # Store the last chunk, which might contain usage information
                        if isinstance(chunk, bytes):
                            chunk_str = (
                                chunk.decode("utf-8", errors="ignore") if chunk else ""
                            )

                            # Check for usage information in the chunk
                            if chunk.startswith(b"data: "):
                                data_str = chunk_str[6:].strip()
                            else:
                                data_str = chunk_str.strip()
                            if data_str and data_str != "[DONE]":
                                try:
                                    data = json.loads(data_str)

                                    # Some providers include usage info in the last chunk
                                    # https://platform.openai.com/docs/api-reference/chat_streaming/streaming#chat_streaming/streaming-usage
                                    if "usage" in data and data["usage"]:
                                        logger.debug(
                                            f"Found usage data in chunk: {data['usage']}"
                                        )
                                        usage = data.get("usage", {})
                                        input_tokens = (
                                            usage.get("prompt_tokens", 0) or 0
                                        ) or input_tokens
                                        output_tokens = (
                                            usage.get("completion_tokens", 0) or 0
                                        ) or output_tokens
                                        total_tokens = usage.get("total_tokens", 0) or total_tokens or (input_tokens + output_tokens)
                                        prompt_tokens_details = usage.get("prompt_tokens_details", {}) or {}
                                        completion_tokens_details = usage.get("completion_tokens_details", {}) or {}
                                        cached_tokens = prompt_tokens_details.get("cached_tokens", 0) or cached_tokens
                                        reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0) or reasoning_tokens or (total_tokens - input_tokens - output_tokens)

                                        # re-calculate output tokens
                                        output_tokens = max(output_tokens, total_tokens - input_tokens)

                                    # Extract content from the chunk based on OpenAI format
                                    if "choices" in data:
                                        for choice in data["choices"]:
                                            if (
                                                "delta" in choice
                                                and "content" in choice["delta"]
                                            ):
                                                content = choice["delta"]["content"]
                                                # Only count tokens if we don't have final usage data
                                                if content:
                                                    # Count tokens in content (approx)
                                                    approximate_output_tokens += (
                                                        len(content) // 4
                                                    )
                                except json.JSONDecodeError:
                                    # If JSON parsing fails, just continue
                                    pass

                        # Yield the chunk unchanged
                        yield chunk

                    logger.debug(
                        f"Streaming complete for {provider_name}. Chunks processed: {chunks_processed}"
                    )

                except Exception as e:
                    # Use parameterized logging to avoid issues if the error message contains braces
                    logger.error(
                        "Error in streaming response: {}", str(e), exc_info=True
                    )
                    # Re-raise to propagate the error
                    raise
                finally:
                    logger.debug(
                        f"Logging API request final details: provider={provider_name}, "
                        f"model={actual_model}, input_tokens={input_tokens}, "
                        f"output_tokens={output_tokens}, cached_tokens={cached_tokens}, reasoning_tokens={reasoning_tokens}"
                    )

                    asyncio.create_task(
                        update_usage_in_background(
                            usage_tracker_id,
                            input_tokens or approximate_input_tokens,
                            output_tokens or approximate_output_tokens,
                            cached_tokens,
                            reasoning_tokens,
                        )
                    )

            return token_counting_stream()


async def create_default_tensorblock_provider_for_user(
    user_id: int, db: AsyncSession
) -> None:
    """
    Create a default TensorBlock provider key for a new user.
    This allows users to use Forge immediately without binding their own API keys.
    """
    from app.models.provider_key import ProviderKey as ProviderKeyModel
    from app.services.providers.tensorblock_adapter import TensorblockAdapter

    # Get TensorBlock configuration from environment variables
    tensorblock_base_url = os.getenv("TENSORBLOCK_BASE_URL")
    tensorblock_api_key = os.getenv("TENSORBLOCK_API_KEY")
    tensorblock_api_version = os.getenv("TENSORBLOCK_API_VERSION")

    if (
        not tensorblock_base_url
        or not tensorblock_api_key
        or not tensorblock_api_version
    ):
        # Log warning but don't fail - TensorBlock is optional
        logger.warning(
            f"TensorBlock environment variables not configured. Skipping default provider creation for user {user_id}"
        )
        return

    try:
        # Create TensorBlock adapter to serialize the API key config
        config = {"api_version": tensorblock_api_version}
        adapter = TensorblockAdapter("tensorblock", tensorblock_base_url, config)
        serialized_api_key_config = adapter.serialize_api_key_config(
            tensorblock_api_key, config
        )

        # Create the provider key
        provider_key = ProviderKeyModel(
            provider_name="TensorBlock",
            encrypted_api_key=encrypt_api_key(serialized_api_key_config),
            user_id=user_id,
            base_url=tensorblock_base_url,
            billable=True,
            model_mapping=None,  # TensorBlock adapter handles model mapping internally
        )

        db.add(provider_key)
        await db.commit()

        logger.info(f"Created default TensorBlock provider for user {user_id}")

    except Exception as e:
        await db.rollback()
        logger.error(
            "Error creating default TensorBlock provider for user {}: {}",
            user_id,
            e,
        )
        # Don't raise the exception - this is optional functionality
