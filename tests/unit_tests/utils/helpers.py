import json
from unittest.mock import Mock
from aiohttp.client_exceptions import ClientResponseError


class AsyncIterator:
    def __init__(self, data):
        self.data = data
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        chunk = self.data[self.index]
        self.index += 1
        return chunk.encode("utf-8")

    def iter_chunks(self, chunk_size=1024):
        """Method expected by Google adapter for streaming"""
        return self._iter_chunks_async(chunk_size)

    async def _iter_chunks_async(self, chunk_size=1024):
        """Async generator for chunk iteration"""
        for item in self.data:
            if isinstance(item, str):
                # For string data, yield as bytes
                yield (item.encode("utf-8"), True)
            else:
                # For other data, convert to JSON string then bytes
                yield (json.dumps(item).encode("utf-8"), True)


class ClientResponse:
    def __init__(self, json_data: dict, status: int = 200):
        self.json_data = json_data
        self.status = status
        # For streaming responses, json_data should be a list of strings
        if isinstance(json_data, list):
            self._content = AsyncIterator(json_data)
        else:
            self._content = AsyncIterator([json.dumps(json_data)])

    @property
    def content(self):
        return self._content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def json(self):
        return self.json_data

    async def read(self):
        return json.dumps(self.json_data).encode("utf-8")

    def raise_for_status(self):
        if self.status >= 400:
            raise ClientResponseError(Mock(), Mock(), status=self.status)


class ClientSessionMock:
    def __init__(self, responses=None, *_, **__):
        self.responses = responses or []
        self.posted_json = []
        self.posted_urls = []
        self.get_urls = []

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    def get(self, url, *args, **kwargs):
        self.get_urls.append(url)
        j, status = self.responses.pop(0)
        return ClientResponse(j, status)

    def post(self, url, *args, **kwargs):
        self.posted_urls.append(url)
        self.posted_json.append(kwargs.get("json", kwargs.get("data")))
        j, status = self.responses.pop(0)
        return ClientResponse(j, status)


OPENAAI_STANDARD_CHAT_COMPLETION_RESPONSE = "Hello! I'm just a program, so I don't have feelings, but I'm here and ready to help you. How can I assist you today?"
OPENAI_STANDARD_RESPONSES_RESPONSE = "Hello! I'm doing well, thank you. How about you?"
ANTHROPIC_STANDARD_CHAT_COMPLETION_RESPONSE = "Hello! I'm doing well, thank you for asking. I'm here and ready to help with whatever you'd like to discuss or work on. How are you doing today?"
GOOGLE_STANDARD_CHAT_COMPLETION_RESPONSE = (
    "I am doing well, thank you for asking. How are you today?\n"
)


def validate_chat_completion_response(
    response: dict,
    expected_model: str = None,
    expected_message: str = None,
    expected_usage: dict = None,
):
    # validate the structure of the response
    assert "model" in response, "model is required"
    assert "choices" in response, "choices is required"
    assert "usage" in response, "usage is required"

    if expected_model:
        assert response["model"] == expected_model
    if expected_message:
        assert response["choices"][0]["message"]["content"] == expected_message
    if expected_usage:
        usage = response["usage"]
        assert usage["prompt_tokens"] == expected_usage["prompt_tokens"]
        assert usage["completion_tokens"] == expected_usage["completion_tokens"]


def process_openai_streaming_response(response: str, result: dict):
    # process the openai streaming response to get the final response
    # extract the model name, response msg and usage info
    # return a dict with the model name, response msg and usage info
    if not response.startswith("data: "):
        return
    response = response[6:].strip()
    if response == "[DONE]":
        return

    data = json.loads(response)
    model = data.get("model")
    if model:
        result["model"] = model

    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
    result["content"] = result.get("content", "") + content

    usage = data.get("usage", {})
    result_usage = result.get("usage", {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_tokens_details": {
            "cached_tokens": 0,
        },
        "completion_tokens_details": {
            "reasoning_tokens": 0,
        },
    })
    if usage:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        result_usage["prompt_tokens"] = prompt_tokens
        result_usage["completion_tokens"] = completion_tokens
        result_usage["total_tokens"] = total_tokens
        result_usage["prompt_tokens_details"]["cached_tokens"] = cached_tokens
        result_usage["completion_tokens_details"]["reasoning_tokens"] = reasoning_tokens
        result["usage"] = result_usage


def validate_chat_completion_streaming_response(
    response: str,
    expected_model: str = None,
    expected_message: str = None,
    expected_usage: dict = None,
):
    if expected_model:
        assert response["model"] == expected_model
    if expected_message:
        assert response["content"] == expected_message
    if expected_usage:
        usage = response["usage"]
        assert usage["prompt_tokens"] == expected_usage["prompt_tokens"]
        assert usage["completion_tokens"] == expected_usage["completion_tokens"]
        if "prompt_tokens_details" in expected_usage:
            expected_usage["prompt_tokens_details"] = usage["prompt_tokens_details"]
        if "completion_tokens_details" in expected_usage:
            expected_usage["completion_tokens_details"] = usage["completion_tokens_details"]

def validate_responses_response(
    response: dict,
    expected_model: str = None,
    expected_message: str = None,
    expected_usage: dict = None,
):
    assert "model" in response, "model is required"
    assert "output" in response, "output is required"
    assert "usage" in response, "usage is required"

    if expected_model:
        assert response["model"] == expected_model
    if expected_message:
        assert response["output"][0]["content"][0]["text"] == expected_message
    if expected_usage:
        usage = response["usage"]
        assert usage["input_tokens"] == expected_usage["input_tokens"]
        assert usage["output_tokens"] == expected_usage["output_tokens"]
