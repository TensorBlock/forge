"""DEPRECATED – legacy Google Gemini adapter

This class predates Google’s official OpenAI-compatible endpoint.  All new code
should use `GeminiOpenAIAdapter` instead (see `gemini_openai_adapter.py`), which
wraps the same functionality via the standardized REST surface.

`GoogleAdapter` is retained temporarily to avoid breaking existing integrations
and for reference while migrating any bespoke features that haven’t yet been
replicated in the new adapter. **It will be removed in a future release.**
"""
import json
import os
import time
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any

import aiohttp

from app.core.logger import get_logger
from app.exceptions.exceptions import BaseForgeException, BaseInvalidRequestException, ProviderAPIException, InvalidCompletionRequestException, \
    InvalidEmbeddingsRequestException

from .base import ProviderAdapter

# Configure logging
logger = get_logger(name="google_adapter")


class GoogleAdapter(ProviderAdapter):
    def __init__(
        self,
        provider_name: str,
        base_url: str,
        config: dict[str, Any],
    ):
        self._provider_name = provider_name
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_mapping(self) -> dict[str, str]:
        return self.GOOGLE_MODEL_MAPPING

    def get_mapped_model(self, model: str) -> str:
        """Get the Google-specific model name"""
        return self.GOOGLE_MODEL_MAPPING.get(model, model)

    async def list_models(self, api_key: str) -> list[str]:
        """List all models (verbosely) supported by the provider"""
        # Check cache first
        cached_models = self.get_cached_models(api_key, self._base_url)
        if cached_models is not None:
            return cached_models

        # If not in cache, make API call
        url = f"{self._base_url}/models"

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, params={"pageSize": 100, "key": api_key}) as response,
        ):
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"List Models API error for {self.provider_name}: {error_text}")
                raise ProviderAPIException(
                    provider_name=self.provider_name,
                    error_code=response.status,
                    error_message=error_text
                )
            resp = await response.json()
            self.GOOGLE_MODEL_MAPPING = {
                d["displayName"]: d["name"] for d in resp["models"]
            }
            models = [d["name"] for d in resp["models"]]

            # Cache the results
            self.cache_models(api_key, self._base_url, models)

            return models

    @staticmethod
    async def upload_file_to_gemini(
        session: aiohttp.ClientSession,
        file_url: str,
        api_key: str,
        display_name: str | None = None,
    ) -> str:
        """
        Upload a file to Google Gemini API using a file URL.
        Uses streaming to handle large files efficiently.

        Args:
            session: aiohttp ClientSession
            file_url: URL of the file to upload
            api_key: Google Gemini API key
            display_name: Optional display name for the file

        Returns:
            dict: Response from the API containing file information
        """
        base_url = "https://generativelanguage.googleapis.com/upload/v1beta/files"
        # First, get the file metadata from the URL
        async with session.head(file_url) as response:
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"Gemini Upload API error: Failed to fetch file metadata from URL: {error_text}")
                raise ProviderAPIException(
                    provider_name="google",
                    error_code=response.status,
                    error_message=error_text
                )

            mime_type = response.headers.get("Content-Type", "application/octet-stream")
            file_size = int(response.headers.get("Content-Length", 0))

        # Prepare the initial request for resumable upload
        headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }

        # Initial request to get upload URL
        metadata = {
            "file": {"display_name": display_name or os.path.basename(file_url)}
        }

        async with session.post(
            f"{base_url}?key={api_key}", headers=headers, json=metadata
        ) as response:
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                logger.error(f"Gemini Upload API error: Failed to initiate upload: {error_text}")
                raise ProviderAPIException(
                    provider_name="google",
                    error_code=response.status,
                    error_message=error_text
                )

            upload_url = response.headers.get("X-Goog-Upload-URL")
            if not upload_url:
                error_text = "Gemini Upload API error: No upload URL received from server"
                logger.error(error_text)
                raise ProviderAPIException(
                    provider_name="google",
                    error_code=404,
                    error_message=error_text
                )

        # Upload the file content using streaming
        upload_headers = {
            "Content-Length": str(file_size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }

        # Stream the file content directly from the source URL to Gemini API
        async with session.get(file_url) as source_response:
            if source_response.status != HTTPStatus.OK:
                error_text = await source_response.text()
                logger.error(f"Gemini Upload API error: Failed to fetch file content: {error_text}")
                raise ProviderAPIException(
                    provider_name="google",
                    error_code=source_response.status,
                    error_message=error_text
                )

            async with session.put(
                upload_url, headers=upload_headers, data=source_response.content
            ) as upload_response:
                if upload_response.status != HTTPStatus.OK:
                    error_text = await upload_response.text()
                    logger.error(f"Gemini Upload API error: Failed to upload file: {error_text}")
                    raise ProviderAPIException(
                        provider_name="google",
                        error_code=upload_response.status,
                        error_message=error_text
                    )

                return await upload_response.json()

    @staticmethod
    async def convert_openai_image_content_to_google(
        msg: dict[str, Any], api_key: str
    ) -> dict[str, Any]:
        """Convert OpenAI image content model to Google Gemini format"""
        data_url = msg["image_url"]["url"]
        if data_url.startswith("data:"):
            # Extract media type and base64 data
            parts = data_url.split(",", 1)
            media_type = parts[0].split(":")[1].split(";")[0]  # e.g., "image/jpeg"
            base64_data = parts[1]  # The actual base64 string without prefix
            return {
                "inline_data": {
                    "mime_type": media_type,
                    "data": base64_data,
                }
            }
        else:
            # download the image and upload it to Google Gemini
            # https://ai.google.dev/api/files#files_create_image-SHELL
            try:
                async with aiohttp.ClientSession() as session:
                    result = await GoogleAdapter.upload_file_to_gemini(
                        session, data_url, api_key
                    )
                return {
                    "file_data": {
                        "mime_type": result["file"]["mimeType"],
                        "file_uri": result["file"]["uri"],
                    }
                }
            except ProviderAPIException as e:
                raise e
            except Exception as e:
                error_text = f"Error uploading image to Google Gemini: {e}"
                logger.error(error_text)
                raise ProviderAPIException(
                    provider_name="google",
                    error_code=400,
                    error_message=error_text
                )

    @staticmethod
    async def convert_openai_content_to_google(
        content: list[dict[str, Any]] | str,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Convert OpenAI content model to Google Gemini format"""
        if isinstance(content, str):
            return [{"text": content}]

        try:
            result = []
            for msg in content:
                _type = msg["type"]
                if _type == "text":
                    result.append({"text": msg["text"]})
                elif _type == "image_url":
                    result.append(
                        await GoogleAdapter.convert_openai_image_content_to_google(
                            msg, api_key
                        )
                    )
                else:
                    error_text = f"{_type} is not supported"
                    logger.error(error_text)
                    raise InvalidCompletionRequestException(
                        provider_name="google",
                        error=ValueError(error_text)
                    )
            return result
        except BaseForgeException as e:
            raise e
        except Exception as e:
            logger.error(f"Error converting OpenAI content to Google: {e}")
            raise BaseInvalidRequestException(
                provider_name="google",
                error=e
            )

    async def process_completion(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any] | AsyncGenerator[bytes, None]:
        if endpoint != "chat/completions":
            raise NotImplementedError(
                f"Google adapter doesn't support endpoint {endpoint}"
            )

        # For chat completions, delegate to appropriate method
        is_streaming = payload.get("stream", False)

        if is_streaming:
            # Convert OpenAI payload to Google format for streaming
            model = payload.get("model", "")
            google_payload = await self.convert_openai_completion_payload_to_google(
                payload, api_key
            )

            # Return the stream generator directly
            return self._stream_google_response(api_key, model, google_payload)
        else:
            try:
                # For non-streaming, process normally
                response = await self._process_google_chat_completion(api_key, payload)
                return response
            except Exception as e:
                logger.error(f"Error processing Google chat completion: {str(e)}")
                raise

    async def _stream_google_response(
        self, api_key: str, model: str, google_payload: dict[str, Any]
    ) -> AsyncGenerator[bytes, None]:
        model_path = model if model.startswith("models/") else f"models/{model}"
        url = f"{self._base_url}/{model_path}:streamGenerateContent"

        initial_chunk = {"choices": [{"delta": {"role": "assistant"}, "index": 0}]}
        yield f"data: {json.dumps(initial_chunk)}\n\n".encode()

        request_id = f"chatcmpl-{uuid.uuid4()}"

        try:
            if not google_payload:
                error_text = f"Empty payload for {self.provider_name} API request"
                logger.error(error_text)
                raise InvalidCompletionRequestException(
                   provider_name=self.provider_name,
                    error=ValueError(error_text)
                )
            if not api_key:
                error_text = f"Missing API key for {self.provider_name} API request"
                logger.error(error_text)
                raise InvalidCompletionRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_text)
                )
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            logger.debug(
                f"Google API request - URL: {url}, Payload sample: {str(google_payload)[:200]}..."
            )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, params={"key": api_key}, json=google_payload, headers=headers
                ) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Completion Streaming API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response.status,
                        error_message=error_text
                    )

                # Process response in chunks
                # https://ai.google.dev/api/generate-content#v1beta.GenerateContentResponse
                buffer = ""
                async for chunk in response.content.iter_chunks():
                    if not chunk[0]:  # Empty chunk
                        continue

                    buffer += chunk[0].decode("utf-8")

                    # Try to find complete JSON objects in the buffer
                    while True:
                        try:
                            # Find the start of a JSON object
                            usage_data = None
                            openai_chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": ""}}],
                            }
                            start_idx = buffer.find("{")
                            if start_idx == -1:
                                break

                            # Try to parse from the start of the object
                            json_obj = json.loads(buffer[start_idx:])
                            # If successful, process the object and remove it from buffer
                            buffer = buffer[:start_idx]

                            # Process the JSON object
                            if "usageMetadata" in json_obj:
                                usage_data = self.format_google_usage(
                                    json_obj["usageMetadata"]
                                )

                            if "candidates" in json_obj:
                                choices = []
                                for c_idx, candidate in enumerate(
                                    json_obj.get("candidates", [])
                                ):
                                    content = candidate.get("content", {})
                                    text_content = "".join(
                                        p.get("text", "")
                                        for p in content.get("parts", [])
                                    )
                                    finish_reason = candidate.get("finishReason")

                                    choices.append({
                                        "index": c_idx,
                                        "delta": {"content": text_content},
                                        **({"finish_reason": finish_reason.lower()
                                        if finish_reason
                                        else {}})
                                    })
                                if not choices:
                                    choices = [{"index": 0, "delta": {"content": ""}}]

                                openai_chunk["choices"] = choices

                            if usage_data:
                                openai_chunk["usage"] = usage_data

                            yield f"data: {json.dumps(openai_chunk)}\n\n".encode()

                        except json.JSONDecodeError:
                            # Incomplete JSON, wait for more data
                            break

            # Send final [DONE] message
            yield b"data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Google streaming API error: {str(e)}", exc_info=True)
            error_chunk = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "error"}],
                "error": {"message": str(e), "type": "api_error"},
            }
            yield f"data: {json.dumps(error_chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

    @staticmethod
    def format_google_usage(metadata: dict) -> dict:
        """Format Google usage metadata to OpenAI format"""
        if not metadata:
            return None
        prompt_tokens = metadata.get("promptTokenCount", 0)
        completion_tokens = metadata.get("candidatesTokenCount", 0)
        cached_tokens = metadata.get("cachedContentTokenCount", 0)
        reasoning_tokens = metadata.get("thoughtsTokenCount", 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_tokens_details": {"cached_tokens": cached_tokens},
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        }

    @staticmethod
    async def convert_openai_completion_payload_to_google(
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Convert OpenAI-format completion payload to Google Gemini format"""
        google_payload = {
            "generationConfig": {
                "stopSequences": payload.get("stop", []),
                "temperature": payload.get("temperature", 0.7),
                "topP": payload.get("top_p", 0.95),
                "maxOutputTokens": payload.get("max_completion_tokens", payload.get("max_tokens", 2048)),
            },
        }

        messages = payload.get("messages", [])

        # Process messages
        google_contents = []
        system_content = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            content = await GoogleAdapter.convert_openai_content_to_google(
                content, api_key
            )

            if role == "system":
                # Google requires a system message to be string
                # https://ai.google.dev/gemini-api/docs/text-generation#system-instructions
                assert isinstance(msg.get("content", ""), str)
                system_content.append(content)
            elif role == "user":
                google_contents.append({"parts": content, "role": "user"})
            elif role == "assistant":
                google_contents.append({"parts": content, "role": "model"})

        # Add system instruction if present
        if system_content:
            google_payload["systemInstruction"] = {"parts": system_content}

        google_payload["contents"] = google_contents

        return google_payload

    async def _process_google_chat_completion(
        self, api_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a regular (non-streaming) chat completion with Google Gemini"""
        model = payload.get("model", "")

        # Convert payload to Google format
        google_payload = await self.convert_openai_completion_payload_to_google(payload, api_key)

        # Properly format the model name for the API request using ternary operator
        model_path = model if model.startswith("models/") else f"models/{model}"

        url = f"{self._base_url}/{model_path}:generateContent"

        try:
            # Make the API request
            headers = {"Content-Type": "application/json", "Accept": "application/json"}

            # Check for API key
            if not api_key:
                error_text = f"Missing API key for {self.provider_name} API request"
                logger.error(error_text)
                raise InvalidCompletionRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_text)
                )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, params={"key": api_key}, json=google_payload, headers=headers
                ) as response,
            ):
                response_status = response.status
                if response_status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Completion API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response_status,
                        error_message=error_text
                    )

                response_json = await response.json()

                # Convert to OpenAI format
                return self.convert_google_completion_response_to_openai(response_json, model)
        except BaseForgeException as e:
            raise e
        except Exception as e:
            logger.error(f"Error in Google chat completion: {str(e)}", exc_info=True)
            raise BaseInvalidRequestException(
                provider_name=self.provider_name,
                error=e
            )

    @staticmethod
    def convert_google_completion_response_to_openai(
        google_response: dict[str, Any], model: str
    ) -> dict[str, Any]:
        """Convert Google completion response format to OpenAI format"""
        # https://ai.google.dev/api/generate-content#v1beta.GenerateContentResponse
        openai_response = {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0}},
        }

        # Extract the candidates
        candidates = google_response.get("candidates", [])
        if not candidates:
            logger.warning("No candidates in Google response")
            openai_response["choices"] = [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "error",
                }
            ]
            return openai_response

        # Process each candidate
        for i, candidate in enumerate(candidates):
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Extract text from parts
            text_content = ""
            for part in parts:
                if "text" in part:
                    text_content += part["text"]

            # Determine finish reason
            finish_reason = candidate.get("finishReason", "").lower()
            if not finish_reason:
                finish_reason = "stop"

            # Add to choices
            openai_response["choices"].append(
                {
                    "index": i,
                    "message": {"role": "assistant", "content": text_content},
                    "finish_reason": finish_reason,
                }
            )

        # Set usage estimates if available
        usage_data = GoogleAdapter.format_google_usage(google_response.get("usageMetadata"))
        if usage_data:
            openai_response["usage"] = usage_data

        return openai_response
    
    @staticmethod
    def convert_openai_embeddings_payload_to_google(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI-format embeddings payload to Google Gemini format"""
        google_payload = {}
        if "dimensions" in payload:
            google_payload["outputDimensionality"] = payload["dimensions"]
        
        input = payload['input']
        if isinstance(input, str):
            google_payload["content"] = {"parts": [{"text": input}]}
        elif isinstance(input, list):
            google_payload["content"] = {"parts": [{"text": text} for text in input]}
        
        return google_payload
    
    @staticmethod
    def convert_google_embeddings_response_to_openai(response_json: dict[str, Any], model: str) -> dict[str, Any]:
        """Convert Google embeddings response format to OpenAI format"""
        openai_response = {
            "object": "list",
            "data": [],
            "model": model,
            # Google doesn't provide the usage metadata for embeddings
            "usage": {
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        }
        values = response_json["embedding"]["values"]
        if values:
            openai_response["data"] = [{
                "object": "embedding",
                "embedding": values,
                "index": 0,
            }]
        
        return openai_response
    
    
    async def process_embeddings(
        self,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        # https://ai.google.dev/api/embeddings
        """Process a embeddings request using Google API"""
        model = payload["model"]

        # Properly format the model name for the API request using ternary operator
        model_path = model if model.startswith("models/") else f"models/{model}"

        url = f"{self._base_url}/{model_path}:embedContent"

        # Convert payload to Google format
        google_payload = self.convert_openai_embeddings_payload_to_google(payload)

        try:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}

            # Check for API key
            if not api_key:
                error_text = f"Missing API key for {self.provider_name} API request"
                logger.error(error_text)
                raise InvalidEmbeddingsRequestException(
                    provider_name=self.provider_name,
                    error=ValueError(error_text)
                )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, params={"key": api_key}, json=google_payload, headers=headers
                ) as response,
            ):
                response_status = response.status
                if response_status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"Embeddings API error for {self.provider_name}: {error_text}")
                    raise ProviderAPIException(
                        provider_name=self.provider_name,
                        error_code=response_status,
                        error_message=error_text
                    )

                response_json = await response.json()
                return self.convert_google_embeddings_response_to_openai(response_json, model)
        except BaseForgeException as e:
            raise e
        except Exception as e:
            logger.error(f"Error in {self.provider_name} embeddings: {str(e)}", exc_info=True)
            raise BaseInvalidRequestException(
                provider_name=self.provider_name,
                error=e
            )
