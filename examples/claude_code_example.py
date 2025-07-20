#!/usr/bin/env python3
"""
Example usage of the Claude Code compatible API endpoints in Forge.

This example demonstrates how to make requests to the new Claude Code endpoints
that accept Anthropic format and route through Forge's provider infrastructure.
"""

import json
import requests

# Configuration
FORGE_BASE_URL = "http://localhost:8000/v1"
FORGE_API_KEY = "forge-your-api-key-here"  # Replace with your actual Forge API key

headers = {
    "Authorization": f"Bearer {FORGE_API_KEY}",
    "Content-Type": "application/json",
}


def test_non_streaming_request():
    """Test a non-streaming Claude Code request."""
    print("🧪 Testing non-streaming Claude Code request...")
    
    request_data = {
        "model": "claude-3-haiku-20240307",  # This will be routed through Forge
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": "Hello! Can you help me understand how Forge works?"
            }
        ],
        "system": "You are a helpful assistant explaining the Forge AI middleware service.",
        "temperature": 0.7
    }
    
    response = requests.post(
        f"{FORGE_BASE_URL}/messages",
        headers=headers,
        json=request_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"Model: {result['model']}")
        print(f"Content: {result['content'][0]['text']}")
        print(f"Usage: {result['usage']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_streaming_request():
    """Test a streaming Claude Code request."""
    print("\n🧪 Testing streaming Claude Code request...")
    
    request_data = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user", 
                "content": "Tell me a short story about AI."
            }
        ],
        "stream": True,
        "temperature": 0.8
    }
    
    response = requests.post(
        f"{FORGE_BASE_URL}/messages",
        headers=headers,
        json=request_data,
        stream=True
    )
    
    if response.status_code == 200:
        print("✅ Streaming response:")
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    if data_str != '[DONE]':
                        try:
                            event_data = json.loads(data_str)
                            if event_data.get('type') == 'content_block_delta':
                                delta = event_data.get('delta', {})
                                if delta.get('type') == 'text_delta':
                                    print(delta.get('text', ''), end='', flush=True)
                        except json.JSONDecodeError:
                            continue
        print("\n✅ Streaming completed!")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_token_counting():
    """Test the token counting endpoint."""
    print("\n🧪 Testing token counting...")
    
    request_data = {
        "model": "claude-3-haiku-20240307",
        "messages": [
            {
                "role": "user",
                "content": "This is a test message to count tokens."
            },
            {
                "role": "assistant", 
                "content": "I understand. I'll help you count the tokens in this conversation."
            }
        ],
        "system": "You are a helpful assistant."
    }
    
    response = requests.post(
        f"{FORGE_BASE_URL}/messages/count_tokens",
        headers=headers,
        json=request_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Token count: {result['input_tokens']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_tool_usage():
    """Test Claude Code with tool usage."""
    print("\n🧪 Testing tool usage...")
    
    request_data = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 200,
        "messages": [
            {
                "role": "user",
                "content": "What's the weather like in San Francisco?"
            }
        ],
        "tools": [
            {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The location to get weather for"
                        }
                    },
                    "required": ["location"]
                }
            }
        ],
        "tool_choice": {"type": "auto"}
    }
    
    response = requests.post(
        f"{FORGE_BASE_URL}/messages",
        headers=headers,
        json=request_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Tool usage response:")
        for content in result['content']:
            if content['type'] == 'text':
                print(f"Text: {content['text']}")
            elif content['type'] == 'tool_use':
                print(f"Tool: {content['name']}")
                print(f"Input: {content['input']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    print("🚀 Claude Code API Examples for Forge")
    print("=" * 50)
    
    # Test various scenarios
    test_non_streaming_request()
    test_streaming_request() 
    test_token_counting()
    test_tool_usage()
    
    print("\n✨ All tests completed!")
    print("\nNote: Make sure to:")
    print("1. Replace FORGE_API_KEY with your actual Forge API key")
    print("2. Have appropriate provider API keys configured in Forge") 
    print("3. Start the Forge server before running these examples") 