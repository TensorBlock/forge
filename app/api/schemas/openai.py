from typing import Any

from pydantic import BaseModel


class OpenAIContentImageUrlModel(BaseModel):
    url: str


class OpenAIAudioModel(BaseModel):
    data: str
    format: str


class OpenAIContentModel(BaseModel):
    type: str  # One of: "text", "image_url", "input_audio"
    text: str | None = None
    image_url: OpenAIContentImageUrlModel | None = None
    input_audio: OpenAIAudioModel | None = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.type not in ["text", "image_url", "input_audio"]:
            raise ValueError(
                f"Invalid type: {self.type}. Must be one of: text, image_url, input_audio"
            )

        # Validate that the appropriate field is set based on type
        if self.type == "text" and self.text is None:
            raise ValueError("text field must be set when type is 'text'")
        if self.type == "image_url" and self.image_url is None:
            raise ValueError("image_url field must be set when type is 'image_url'")
        if self.type == "input_audio" and self.input_audio is None:
            raise ValueError("input_audio field must be set when type is 'input_audio'")


class ChatMessage(BaseModel):
    role: str
    content: list[OpenAIContentModel] | str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    stream_options: dict[str, Any] | None = None
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    logit_bias: dict[str, float] | None = None
    user: str | None = None
    web_search_options: Any | None = None
    response_format: dict[str, Any] | None = None
    tools: list[Any, Any] | None = None
    tool_choice: str | None = None
    seed: int | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    max_completion_tokens: int | None = None
    metadata: dict[Any, Any] | None = None
    modalities: list[str] | None = None
    parallel_tool_calls: bool | None = True
    prediction: dict[Any, Any] | None = None
    reasoning_effort: str | None = "medium"
    service_tier: str | None = "auto"

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
    suffix: str | None = None
    max_tokens: int | None = 16
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    logprobs: int | None = None
    echo: bool | None = False
    stop: str | list[str] | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    best_of: int | None = 1
    logit_bias: dict[str, float] | None = None
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
