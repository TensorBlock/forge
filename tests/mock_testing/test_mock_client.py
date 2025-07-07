#!/usr/bin/env python3
"""
Test script that demonstrates using the mock client.
This shows how to use the mock client for testing without real API calls.
"""

import argparse
import asyncio
import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the mock client
from app.services.providers.mock_provider import MockClient


async def test_chat_completion(client: MockClient) -> None:
    """Test a standard chat completion"""
    print("\n🧪 Testing chat completion...")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "What can you tell me about using mock providers for testing?",
        },
    ]

    response = await client.chat_completions_create(
        model="mock-gpt-4", messages=messages, temperature=0.7
    )

    print(f"✅ Model: {response.model}")

    # Handle both object-style and dict-style responses
    if hasattr(response.choices[0], "message"):
        print(f"✅ Response: {response.choices[0].message.content}")
    elif isinstance(response.choices[0], dict) and "message" in response.choices[0]:
        print(f"✅ Response: {response.choices[0]['message']['content']}")
    else:
        print(f"✅ Response structure: {response.choices[0]}")

    print(f"✅ Usage: {response.usage}")
    return response


async def test_streaming_chat_completion(client: MockClient) -> None:
    """Test a streaming chat completion"""
    print("\n🧪 Testing streaming chat completion...")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "Explain the benefits of mock testing in a few sentences.",
        },
    ]

    stream = await client.chat_completions_create(
        model="mock-gpt-4", messages=messages, temperature=0.7, stream=True
    )

    print("✅ Streaming response:")
    print("---")

    async for chunk in stream:
        if (
            hasattr(chunk.choices[0].delta, "content")
            and chunk.choices[0].delta.content
        ):
            print(chunk.choices[0].delta.content, end="", flush=True)

    print("\n---")
    print("✅ Streaming completed")


async def test_text_completion(client: MockClient) -> None:
    """Test a text completion"""
    print("\n🧪 Testing text completion...")

    prompt = "Write a short explanation about mock testing:"

    response = await client.completions_create(
        model="mock-gpt-3.5-turbo", prompt=prompt, temperature=0.7
    )

    print(f"✅ Model: {response.model}")

    # Handle both object-style and dict-style responses
    if hasattr(response.choices[0], "text"):
        print(f"✅ Response: {response.choices[0].text}")
    elif isinstance(response.choices[0], dict) and "text" in response.choices[0]:
        print(f"✅ Response: {response.choices[0]['text']}")
    else:
        print(f"✅ Response structure: {response.choices[0]}")

    print(f"✅ Usage: {response.usage}")
    return response


async def test_models_list(client: MockClient) -> None:
    """Test listing available models"""
    print("\n🧪 Testing models list...")

    models = await client.models_list()

    print("✅ Available models:")
    for model in models:
        print(f"  - {model['id']} (owned by {model['owned_by']})")

    return models


async def run_interactive_test(model: str = "mock-gpt-4") -> None:
    """Run an interactive test where the user can input prompts"""
    client = MockClient()

    print("\n💬 Interactive Mock Chat (type 'exit' to quit)")
    print(f"Using model: {model}")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            break

        print("\nAssistant: ", end="", flush=True)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input},
        ]

        stream = await client.chat_completions_create(
            model=model, messages=messages, stream=True
        )

        async for chunk in stream:
            if (
                hasattr(chunk.choices[0].delta, "content")
                and chunk.choices[0].delta.content
            ):
                print(chunk.choices[0].delta.content, end="", flush=True)

        print()


async def main():
    parser = argparse.ArgumentParser(description="Test the mock OpenAI client")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--model",
        "-m",
        default="mock-gpt-4",
        help="Model to use for testing (default: mock-gpt-4)",
    )
    parser.add_argument("--run-all", "-a", action="store_true", help="Run all tests")

    args = parser.parse_args()

    if args.interactive:
        await run_interactive_test(args.model)
        return

    # Initialize the mock client
    client = MockClient()

    # Run all tests
    await test_models_list(client)
    await test_chat_completion(client)
    await test_streaming_chat_completion(client)
    await test_text_completion(client)

    print("\n🎉 All mock client tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
