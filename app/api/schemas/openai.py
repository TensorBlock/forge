from typing import Any

from pydantic import BaseModel, field_validator

from app.core.logger import get_logger
from app.exceptions.exceptions import InvalidCompletionRequestException

logger = get_logger(name="openai_schemas")


class OpenAIContentImageUrlModel(BaseModel):
    url: str


class OpenAIAudioModel(BaseModel):
    data: str
    format: str


class OpenAIContentFileModel(BaseModel):
    filename: str | None = None
    file_data: str | None = None
    file_id: str | None = None

class OpenAIContentModel(BaseModel):
    type: str  # One of: "text", "image_url", "input_audio", "file"
    text: str | None = None
    image_url: OpenAIContentImageUrlModel | None = None
    input_audio: OpenAIAudioModel | None = None
    file: OpenAIContentFileModel | None = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.type not in ["text", "image_url", "input_audio", "file"]:
            error_message = f"Invalid type: {self.type}. Must be one of: text, image_url, input_audio"
            logger.error(error_message)
            raise InvalidCompletionRequestException(
                provider_name="openai",
                error=ValueError(error_message)
            )

        # Validate that the appropriate field is set based on type
        if self.type == "text" and self.text is None:
            error_message = "text field must be set when type is 'text'"
            logger.error(error_message)
            raise InvalidCompletionRequestException(
                provider_name="openai",
                error=ValueError(error_message)
            )
        if self.type == "image_url" and self.image_url is None:
            error_message = "image_url field must be set when type is 'image_url'"
            logger.error(error_message)
            raise InvalidCompletionRequestException(
                provider_name="openai",
                error=ValueError(error_message)
            )
        if self.type == "input_audio" and self.input_audio is None:
            error_message = "input_audio field must be set when type is 'input_audio'"
            logger.error(error_message)
            raise InvalidCompletionRequestException(
                provider_name="openai",
                error=ValueError(error_message)
            )
        if self.type == "file" and self.file is None:
            error_message = "file field must be set when type is 'file'"
            logger.error(error_message)
            raise InvalidCompletionRequestException(
                provider_name="openai",
                error=ValueError(error_message)
            )


# ---------------------------------------------------------------------------
# OpenAI tool call models (for function calling / tool usage)
# ---------------------------------------------------------------------------


class OpenAIToolCallFunctionModel(BaseModel):
    """Represents the function part inside a tool call record."""

    name: str
    # According to the OpenAI specification this is a JSON string, but users often
    # pass a structured object.  Accept both for leniency.
    arguments: Any


class OpenAIToolCallModel(BaseModel):
    """Represents a single tool call entry returned by the assistant."""

    id: str
    type: str
    function: OpenAIToolCallFunctionModel


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message.

    Forge aims to stay 100 % compatible with the OpenAI Chat Completions API.  We
    therefore mirror the message schema defined by OpenAI, while being liberal
    in what we accept so that users can reuse the exact same payloads they send
    to `api.openai.com`.
    """

    role: str
    content: list[OpenAIContentModel] | str | None = None
    name: str | None = None

    # Fields for function calling / tool usage.  They are optional and ignored
    # by most providers, but we must parse (and forward) them to remain API-
    # compatible.
    tool_calls: list[OpenAIToolCallModel] | None = None
    tool_call_id: str | None = None

    # Future-proofing: allow any extra keys that OpenAI may introduce without
    # breaking existing clients.
    class Config:
        extra = "allow"

    # ---------------------------------------------------------------------
    # Validators
    # ---------------------------------------------------------------------

    @classmethod
    def _allow_null_content(cls, v):  # noqa: D401, ANN001
        """Return the value as-is so that **null** is accepted without errors."""
        return v

    # Pydantic v2
    _validate_content = field_validator("content", mode="before")(_allow_null_content)


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str
    audio: object | None = None
    frequency_penalty: float | None = 0.0
    logit_bias: dict[Any, Any] | None = None
    logprobs: bool | None = None
    max_completion_tokens: int | None = None
    max_tokens: int | None = None # deprecated
    metadata: dict[Any, Any] | None = None
    modalities: list[Any] | None = None
    n: int | None = 1
    parallel_tool_calls: bool | None = True
    prediction: object | None = None
    presence_penalty: float | None = 0.0
    reasoning_effort: str | None = "medium"
    response_format: Any | None = None
    seed: int | None = None
    service_tier: str | None = "auto"
    stop: str | list[Any] | None = None
    store: bool | None = False
    stream: bool | None = False
    stream_options: object | None = None
    temperature: float | None = 1.0
    tool_choice: str | dict[Any, Any] | None = None
    tools: list[Any] | None = None
    top_logprobs: int | None = None
    top_p: float | None = 1.0
    user: str | None = None
    web_search_options: object | None = None


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionResponseUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionResponseChoice]
    usage: ChatCompletionResponseUsage | None = None


class CompletionRequest(BaseModel):
    model: str
    prompt: str | list[str]
    best_of: int | None = 1
    echo: bool | None = False
    frequency_penalty: float | None = 0.0
    logit_bias: dict[Any, Any] | None = None
    logprobs: int | None = None
    max_tokens: int | None = 16
    n: int | None = 1
    presence_penalty: float | None = 0.0
    seed: int | None = None
    stop: str | list[str] | None = None
    stream: bool | None = False
    stream_options: object | None = None
    suffix: str | None = None
    temperature: float | None = 1.0
    user: str | None = None


class CompletionResponseChoice(BaseModel):
    text: str
    index: int
    logprobs: Any | None = None
    finish_reason: str | None = None


class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: list[CompletionResponseChoice]
    usage: ChatCompletionResponseUsage | None = None

# https://platform.openai.com/docs/api-reference/images/create
class ImageGenerationRequest(BaseModel):
    prompt: str
    background: str | None = 'auto'
    model: str | None = 'dall-e-2'
    moderation: str | None = 'auto'
    n: int | None = 1
    output_compression: int | None = 100
    output_format: str | None = 'png'
    quality: str | None = 'auto'
    response_format: str | None = 'url'
    size: str | None = 'auto'
    style: str | None = 'vivid'
    user: str | None = None

# https://platform.openai.com/docs/api-reference/images/createEdit
class ImageEditsRequest(BaseModel):
    image: str | list
    prompt: str
    background: str | None = 'auto'
    mask: Any | None = None
    model: str | None = None
    n: int | None = 1
    quality: str | None = 'auto'
    response_format: str | None = 'url'
    size: str | None = '1024x1024'
    user: str | None = None

class EmbeddingsRequest(BaseModel):
    model: str
    input: str | list[str]
    user: str | None = None
    encoding_format: str | None = 'float'
    # inpput_type is for cohere embeddings only
    input_type: str | None = 'search_document'


# ---------------------------------------------------------------------------
# OpenAI Responses Request
# https://platform.openai.com/docs/api-reference/responses/create
# ---------------------------------------------------------------------------
class ResponsesInputTextItem(BaseModel):
    text: str
    type: str  #  always input_text

class ResponsesInputImageItem(BaseModel):
    detail: str | None = 'auto'
    type: str  #  always input_image
    file_id: str | None = None
    image_url: str | None = None

class ResponsesInputFileItem(BaseModel):
    type: str  #  always input_file
    file_data: str | None = None
    file_id: str | None = None
    file_url: str | None = None
    filename: str | None = None

class ResponsesInputAudioItem(BaseModel):
    input_audio: object
    type: str  #  always input_audio

class ResponsesInputMessageItem(BaseModel):
    role: str
    type: str | None = None
    content: str | list[ResponsesInputTextItem | ResponsesInputImageItem | ResponsesInputFileItem | ResponsesInputAudioItem]


class ResponsesItemInputMessage(BaseModel):
    role: str
    content: list[ResponsesInputTextItem | ResponsesInputImageItem | ResponsesInputFileItem | ResponsesInputAudioItem]
    status: str | None = None
    type: str | None = None

class ResponsesItemOutputMessage(BaseModel):
    content: list[object]
    id: str
    role: str
    status: str
    type: str

class ResponsesItemFileSearchToolCall(BaseModel):
    id: str
    query: str
    status: str
    type: str
    results: list[object]

class ResponsesItemComputerToolCall(BaseModel):
    action: object
    call_id: str
    id: str
    pending_safety_checks: list[object]
    status: str
    type: str

class ResponsesItemComputerToolCallOutput(BaseModel):
    call_id: str
    output: object
    type: str
    acknowledged_safety_checks: list[object] | None = None
    id: str | None = None
    status: str | None = None

class ResponsesItemWebSearchToolCall(BaseModel):
    action: object
    id: str
    status: str
    type: str

class ResponsesItemFunctionToolCall(BaseModel):
    arguments: str
    call_id: str
    name: str
    type: str
    id: str | None = None
    status: str | None = None

class ResponsesItemFunctionToolCallOutput(BaseModel):
    call_id: str
    output: str | list[object]
    type: str
    id: str | None = None
    status: str | None = None

class ResponsesItemReasoning(BaseModel):
    id: str
    summary: list[object]
    type: str
    content: list[object] | None = None
    encrypted_content: str | None = None
    status: str | None = None

class ResponsesItemImageGenerationCall(BaseModel):
    id: str
    result: str
    status: str
    type: str

class ResponsesItemCodeInterpreterToolCall(BaseModel):
    code: str
    container_id: str
    id: str
    outputs: list[object]
    status: str
    type: str

class ResponsesItemLocalShellCall(BaseModel):
    action: object
    call_id: str
    id: str
    status: str
    type: str

class ResponsesItemLocalShellCallOutput(BaseModel):
    id: str
    output: str
    type: str
    status: str | None = None

class ResponsesItemMCPListTools(BaseModel):
    id: str
    server_label: str
    tools: list[object]
    type: str
    error: str | None = None

class ResponsesItemMCPApprovalRequest(BaseModel):
    arguments: str
    id: str
    name: str
    server_label: str
    type: str

class ResponsesItemMCPApprovalResponse(BaseModel):
    approval_request_id: str
    approve: bool
    type: str
    id: str | None = None
    reason: str | None = None

class ResponsesItemMCPToolCall(BaseModel):
    arguments: str
    id: str
    name: str
    server_label: str
    type: str
    error: str | None = None
    output: str | None = None

class ResponsesItemCustomToolCallOutput(BaseModel):
    call_id: str
    output: str | list[object]
    type: str
    id: str | None = None

class ResponsesItemCustomToolCall(BaseModel):
    call_id: str
    input: str
    name: str
    type: str
    id: str | None = None

class ResponsesItemReference(BaseModel):
    id: str
    type: str

class ResponsesRequest(BaseModel):
    background: bool | None = False
    conversation: str | object | None = None
    include: list[Any] | None = None
    input: str | list[ResponsesInputMessageItem | ResponsesItemReference | ResponsesItemInputMessage | ResponsesItemFileSearchToolCall | ResponsesItemComputerToolCall | ResponsesItemWebSearchToolCall | ResponsesItemFunctionToolCall | ResponsesItemReasoning | ResponsesItemImageGenerationCall | ResponsesItemCodeInterpreterToolCall | ResponsesItemLocalShellCall | ResponsesItemMCPListTools | ResponsesItemMCPApprovalRequest | ResponsesItemMCPApprovalResponse | ResponsesItemMCPToolCall | ResponsesItemCustomToolCallOutput | ResponsesItemCustomToolCall] | None = None
    instructions: str | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    metadata: dict[Any, Any] | None = None
    model: str | None = None
    parallel_tool_calls: bool | None = True
    previous_response_id: str | None = None
    prompt: object | None = None
    prompt_cache_key: str | None = None
    reasoning: object | None = None
    safety_identifier: str | None = None
    service_tier: str | None = 'auto'
    store: bool | None = True
    stream: bool | None = False
    stream_options: object | None = None
    temperature: float | None = 1.0
    text: object | None = None
    tool_choice: str | object | None = None
    tools: list[Any] | None = None
    top_logprobs: int | None = None
    top_p: float | None = 1.0
    truncation: str | None = 'disabled'
