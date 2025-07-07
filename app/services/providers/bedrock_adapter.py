import aiobotocore.session
import base64
import json
import time
import uuid
import aiohttp
from collections.abc import AsyncGenerator
from typing import Any

from app.core.logger import get_logger
from .base import ProviderAdapter


logger = get_logger(name="bedrock_adapter")

class BedrockAdapter(ProviderAdapter):
    """Adapter for Bedrock API"""

    BEDROCK_FINISH_REASONS_MAPPING = {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "content_filtered": "content_filtered",
    }

    def __init__(self, provider_name: str, base_url: str, config: dict[str, str] | None = None):
        self._provider_name = provider_name
        self._base_url = base_url
        assert "region_name" in config, "Bedrock region_name is required"
        self._region_name = config["region_name"]
        assert "aws_access_key_id" in config, "Bedrock aws_access_key_id is required"
        self._aws_access_key_id = config["aws_access_key_id"]
        assert "aws_secret_access_key" in config, "Bedrock aws_secret_access_key is required"
        self._aws_secret_access_key = config["aws_secret_access_key"]
        self._session = aiobotocore.session.get_session()
    
    @property
    def client_ctx(self):
        return self._session.create_client("bedrock", region_name=self._region_name, aws_access_key_id=self._aws_access_key_id, aws_secret_access_key=self._aws_secret_access_key)
    
    @property
    def runtime_client_ctx(self):
        return self._session.create_client("bedrock-runtime", region_name=self._region_name, aws_access_key_id=self._aws_access_key_id, aws_secret_access_key=self._aws_secret_access_key)

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @staticmethod
    def serialize_api_key_config(api_key: str, config: dict[str, Any] | None) -> str:
        """Serialize the API key for the given provider"""
        assert config is not None
        assert config.get("region_name") is not None
        assert config.get("aws_access_key_id") is not None
        assert config.get("aws_secret_access_key") is not None

        return json.dumps({
            "api_key": api_key,
            "region_name": config["region_name"],
            "aws_access_key_id": config["aws_access_key_id"],
            "aws_secret_access_key": config["aws_secret_access_key"],
        })
    
    @staticmethod
    def deserialize_api_key_config(serialized_api_key_config: str) -> tuple[str, dict[str, Any] | None]:
        """Deserialize the API key for the given provider"""
        deserialized_api_key_config = json.loads(serialized_api_key_config)
        assert deserialized_api_key_config.get("api_key") is not None
        assert deserialized_api_key_config.get("region_name") is not None
        assert deserialized_api_key_config.get("aws_access_key_id") is not None
        assert deserialized_api_key_config.get("aws_secret_access_key") is not None

        return deserialized_api_key_config["api_key"], {
            "region_name": deserialized_api_key_config["region_name"],
            "aws_access_key_id": deserialized_api_key_config["aws_access_key_id"],
            "aws_secret_access_key": deserialized_api_key_config["aws_secret_access_key"],
        }
    
    @staticmethod
    def mask_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
        """Mask the config for the given provider"""
        assert config is not None
        assert config.get("region_name") is not None
        assert config.get("aws_access_key_id") is not None
        assert config.get("aws_secret_access_key") is not None
        mask_str = "*" * 7
        return {
            "region_name": config["region_name"][:3] + mask_str + config["region_name"][-3:],
            "aws_access_key_id": config["aws_access_key_id"][:3] + mask_str + config["aws_access_key_id"][-3:],
            "aws_secret_access_key": config["aws_secret_access_key"][:3] + mask_str + config["aws_secret_access_key"][-3:],
        }


    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock/client/list_foundation_models.html
        # Check cache first
        cached_models = self.get_cached_models(api_key, self._base_url)
        if cached_models is not None:
            return cached_models

        # If not in cache, make API call
        async with self.client_ctx as bedrock:
            try:
                response = await bedrock.list_foundation_models()
            except Exception as e:
                raise ValueError(f"Bedrock API error: {e}")
            
            models = [r["modelId"] for r in response["modelSummaries"]]

            # Cache the results
            self.cache_models(api_key, self._base_url, models)

            return models
    @staticmethod
    async def convert_openai_image_content_to_bedrock(msg: list[dict[str, Any]] | str) -> list[dict[str, Any]]:
        """Convert OpenAI image content to Bedrock format"""
        data_url = msg["image_url"]["url"]
        if data_url.startswith("data:"):
            # Extract media type and base64 data
            parts = data_url.split(",", 1)
            media_type = parts[0].split(":")[1].split(";")[0]  # e.g., "image/jpeg"
            base64_data = parts[1]  # The actual base64 string without prefix
            
            # Convert base64 string to bytes
            image_bytes = base64.b64decode(base64_data)
            return {
                "image": {
                    "format": media_type.split("/")[-1],
                    "source": {
                        "bytes": image_bytes,
                    },
                }
            }
        else:
            # download the image and convert to base64
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(data_url) as response:
                        response.raise_for_status()
                        mime_type = response.headers.get("Content-Type", "image/jpeg")

                    async with session.get(data_url) as response:
                        response.raise_for_status()
                        image_data = await response.read()
                        return {
                            "image": {
                                "format": mime_type.split("/")[-1],
                                "source": {
                                    "bytes": image_data,
                                },
                            }
                        }
            except Exception as e:
                logger.warning(f"Bedrock API error: failed to download image from {data_url}: {e}")
                raise Exception(f"Bedrock API error: {e}")
    
    @staticmethod
    async def convert_openai_content_to_bedrock(content: list[dict[str, Any]] | str) -> list[dict[str, Any]]:
        """Convert OpenAI content to Bedrock format"""
        if isinstance(content, str):
            return [{"text": content}]

        try:
            result = []
            for msg in content:
                _type = msg["type"]
                if _type == "text":
                    result.append({"text": msg["text"]})
                elif _type == "image_url":
                    result.append(await BedrockAdapter.convert_openai_image_content_to_bedrock(msg))
                else:
                    raise NotImplementedError(f"{_type} is not supported")
            return result
        except Exception as e:
            raise NotImplementedError("Unsupported content type") from e

    @staticmethod
    async def convert_openai_payload_to_bedrock(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI payload to Bedrock format"""
        modelId = payload["model"]
        
        inferenceConfig = {}
        if "temperature" in payload:
            inferenceConfig["temperature"] = payload["temperature"]
        if "max_tokens" in payload:
            inferenceConfig["maxTokens"] = payload["max_tokens"]
        if "top_p" in payload:
            inferenceConfig["topP"] = payload["top_p"]
        if "stop" in payload:
            inferenceConfig["stopSequences"] = payload["stop"]
        
        system = []
        messages = []
        for msg in payload["messages"]:
            role = msg["role"]
            content = msg["content"]
            content = await BedrockAdapter.convert_openai_content_to_bedrock(content)

            if role == "system":
                # Bedrock requires system message to be a string
                assert isinstance(msg["content"], str)
                system.append({"text": msg["content"]})
            elif role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
            else:
                raise NotImplementedError(f"Bedrock API error: Role {role} is not supported")
        
        return {
            "modelId": modelId,
            "inferenceConfig": inferenceConfig,
            "system": system,
            "messages": messages,
        }
    

    async def _process_regular_response(self, bedrock_payload: dict[str, Any]) -> dict[str, Any]:
        """Process a regular response from Bedrock API"""
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html
        async with self.runtime_client_ctx as bedrock:
            try:
                response = await bedrock.converse(
                    **bedrock_payload,
                )
            except Exception as e:
                raise ValueError(f"Bedrock API error: {e}")

            if message := response.get("output", {}).get("message"):
                completion_id = f"chatcmpl-{str(uuid.uuid4())}"
                created = int(time.time())
                content = message.get("content", [])
                role = message.get("role", "assistant")

                # Extract text from content blocks
                text_content = ""
                for block in content:
                    for _type, value in block.items():
                        if _type == "text":
                            text_content += value
                        else:
                            raise NotImplementedError(f"Bedrock API error: {_type} response is not supported")
                
                input_tokens = response.get("usage", {}).get("inputTokens", 0)
                output_tokens = response.get("usage", {}).get("outputTokens", 0)
                total_tokens = response.get("usage", {}).get("totalTokens", 0)

                finish_reason = response.get("stopReason", "end_turn")
                finish_reason = self.BEDROCK_FINISH_REASONS_MAPPING.get(finish_reason, "stop")

                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": bedrock_payload["modelId"],
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": role,
                                "content": text_content,
                            },
                            "finish_reason": finish_reason,
                        }
                    ],
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": total_tokens or (input_tokens + output_tokens),
                    },
                }
    
    async def _process_streaming_response(self, bedrock_payload: dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """Process a streaming response from Bedrock API"""
        final_usage_data = None
        finish_reason = None
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(time.time())

        try:
            async with self.runtime_client_ctx as bedrock:
                try:
                    response = await bedrock.converse_stream(
                        **bedrock_payload,
                    )
                    async for event in response["stream"]:
                        # only one key in each event
                        openai_chunk = None
                        if "messageStart" in event:
                            role = event["messageStart"].get("role", "assistant")
                            openai_chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": bedrock_payload["modelId"],
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": role,
                                            "content": "",
                                        },
                                        "finish_reason": None,
                                    }
                                ]
                            }
                        elif "contentBlockDelta" in event:
                            delta_content = event["contentBlockDelta"].get("delta", {}).get("text", "")
                            openai_chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": bedrock_payload["modelId"],
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "content": delta_content,
                                        },
                                        "finish_reason": None,
                                    }
                                ]
                            }
                        elif "contentBlockStart" in event or "contentBlockStop" in event:
                            openai_chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": bedrock_payload["modelId"],
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                        elif "messageStop" in event:
                            finish_reason = event["messageStop"].get("stopReason", "end_turn")
                            finish_reason = self.BEDROCK_FINISH_REASONS_MAPPING.get(finish_reason, "stop")
                            openai_chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": bedrock_payload["modelId"],
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": finish_reason,
                                    }
                                ],
                            }
                        elif "metadata" in event:
                            usage = event["metadata"].get('usage')
                            if usage:
                                input_tokens = usage.get("inputTokens", 0)
                                output_tokens = usage.get("outputTokens", 0)
                                total_tokens = usage.get("totalTokens", 0) or (input_tokens + output_tokens)
                                final_usage_data = {
                                    "prompt_tokens": input_tokens,
                                    "completion_tokens": output_tokens,
                                    "total_tokens": total_tokens,
                                }
                        if openai_chunk:
                            yield f"data: {json.dumps(openai_chunk)}\n\n".encode()
                except Exception as e:
                    raise ValueError(f"Bedrock API error: {e}")
                if final_usage_data:
                    openai_chunk = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": bedrock_payload["modelId"],
                        "choices": [{
                            "index": 0,
                            "delta": {},
                        }],
                        "usage": final_usage_data,
                    }
                    yield f"data: {json.dumps(openai_chunk)}\n\n".encode()

            # Send final [DONE] message
            yield b"data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Bedrock streaming API error: {str(e)}", exc_info=True)
            error_chunk = {
                "id": str(uuid.uuid4()),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": bedrock_payload["modelId"],
                "choices": [{"index": 0, "delta": {}, "finish_reason": "error"}],
                "error": {"message": str(e), "type": "api_error"},
            }
            yield f"data: {json.dumps(error_chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

    
    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> Any:
        """Process a completion request"""
        streaming = payload.get("stream", False)
        bedrock_payload = await BedrockAdapter.convert_openai_payload_to_bedrock(payload)

        if streaming:
            return self._process_streaming_response(bedrock_payload)
        else:
            return await self._process_regular_response(bedrock_payload)
    
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Process a embeddings request"""
        raise NotImplementedError("Bedrock API does not support embeddings")
