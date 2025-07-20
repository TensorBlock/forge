# Claude Code Support in Forge

Forge now supports Claude Code compatible API endpoints, allowing you to use Anthropic's message format while leveraging Forge's provider management and routing capabilities.

## Overview

The Claude Code support enables:
- **Anthropic Format**: Send requests in Anthropic's native message format
- **Provider Agnostic**: Route to any provider supported by Forge (OpenAI, Anthropic, etc.)
- **Seamless Conversion**: Automatic conversion between Anthropic and OpenAI formats
- **Full Feature Support**: Streaming, tools, token counting, and all Anthropic features
- **Forge Integration**: Leverage Forge's API key management, provider routing, and caching

## Endpoints

### POST `/v1/messages`

Main endpoint for Claude Code message completions.

**Request Format (Anthropic Compatible):**
```json
{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 1000,
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "system": "You are a helpful assistant.",
  "temperature": 0.7,
  "stream": false
}
```

**Response Format (Anthropic Compatible):**
```json
{
  "id": "msg_01ABC123DEF456",
  "type": "message",
  "role": "assistant",
  "model": "claude-3-haiku-20240307",
  "content": [
    {
      "type": "text",
      "text": "Hello! I'm doing well, thank you for asking."
    }
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 12
  }
}
```

### POST `/v1/messages/count_tokens`

Estimates token count for Anthropic messages.

**Request:**
```json
{
  "model": "claude-3-haiku-20240307",
  "messages": [
    {
      "role": "user", 
      "content": "Count tokens for this message."
    }
  ],
  "system": "You are a helpful assistant."
}
```

**Response:**
```json
{
  "input_tokens": 15
}
```

## Features

### 1. Non-Streaming Requests

Standard request-response pattern with complete message returned at once.

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/messages",
    headers={"Authorization": "Bearer forge-your-api-key"},
    json={
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)
```

### 2. Streaming Requests

Server-Sent Events (SSE) for real-time response streaming.

```python
response = requests.post(
    "http://localhost:8000/v1/messages",
    headers={"Authorization": "Bearer forge-your-api-key"},
    json={
        "model": "claude-3-haiku-20240307", 
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Tell me a story"}],
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line.startswith(b'data: '):
        # Process SSE events
        pass
```

### 3. Tool Usage

Support for function calling with tools.

```json
{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 200,
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in NYC?"
    }
  ],
  "tools": [
    {
      "name": "get_weather",
      "description": "Get weather for a location",
      "input_schema": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        },
        "required": ["location"]
      }
    }
  ],
  "tool_choice": {"type": "auto"}
}
```

### 4. Multimodal Support

Support for images in user messages.

```json
{
  "model": "claude-3-haiku-20240307",
  "max_tokens": 100, 
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's in this image?"
        },
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": "/9j/4AAQSkZJRgABAQEA..."
          }
        }
      ]
    }
  ]
}
```

## How It Works

1. **Request Reception**: Claude Code endpoint receives Anthropic format request
2. **Format Conversion**: Request is converted to OpenAI format 
3. **Forge Routing**: Converted request is routed through Forge's provider system
4. **Provider Processing**: Request is sent to the appropriate provider (OpenAI, Anthropic, etc.)
5. **Response Conversion**: Provider response is converted back to Anthropic format
6. **Client Response**: Anthropic-formatted response is returned to client

## Configuration

### API Keys

Use your existing Forge API key for authentication:

```bash
curl -X POST "http://localhost:8000/v1/messages" \
  -H "Authorization: Bearer forge-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-haiku-20240307",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Model Routing

Models are routed through Forge's provider configuration:
- `claude-3-haiku-20240307` → Routed to configured Claude provider
- `gpt-4` → Routed to configured OpenAI provider
- Custom model mappings work as configured in Forge

### Provider Scope

Claude Code endpoints respect Forge API key provider scopes:
- If your Forge key is scoped to specific providers, only those providers will be accessible
- Unrestricted keys can access all configured providers

## Error Handling

Errors are returned in Anthropic format:

```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "Missing required field: max_tokens"
  }
}
```

Error types match Anthropic's error taxonomy:
- `invalid_request_error`: Invalid request format
- `authentication_error`: Invalid API key
- `rate_limit_error`: Rate limit exceeded
- `api_error`: Provider API error

## Supported Parameters

### Required
- `model`: Model name (routed through Forge)
- `max_tokens`: Maximum tokens to generate
- `messages`: Array of message objects

### Optional
- `system`: System prompt (string or array)
- `temperature`: Sampling temperature (0.0 to 1.0)
- `top_p`: Nucleus sampling parameter
- `top_k`: Top-k sampling (logged but ignored - not supported by OpenAI)
- `stop_sequences`: Array of stop sequences
- `stream`: Enable streaming (default: false)
- `tools`: Array of tool definitions
- `tool_choice`: Tool choice strategy
- `metadata`: Request metadata

## Examples

See `examples/claude_code_example.py` for comprehensive usage examples including:
- Non-streaming requests
- Streaming requests  
- Token counting
- Tool usage
- Error handling

## Migration from Direct Anthropic API

To migrate from direct Anthropic API usage:

1. **Change Base URL**: Update from `https://api.anthropic.com/v1` to your Forge instance
2. **Update Authentication**: Use your Forge API key instead of Anthropic API key
3. **Keep Request Format**: No changes needed to request/response format
4. **Benefit from Forge**: Gain provider flexibility, key management, and routing

## Performance Considerations

- **Conversion Overhead**: Minimal latency added for format conversion
- **Streaming Efficiency**: SSE events are converted in real-time
- **Token Counting**: Uses tiktoken for accurate token estimation
- **Caching**: Leverages Forge's existing caching infrastructure

## Limitations

- `top_k` parameter is accepted but ignored (OpenAI doesn't support it)
- Some advanced Anthropic features may not be available depending on target provider
- Provider-specific model capabilities apply (e.g., vision support) 