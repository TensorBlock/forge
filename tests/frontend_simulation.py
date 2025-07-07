import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import dotenv_values, load_dotenv

# Load directly from .env file, bypassing system environment variables
env_values = dotenv_values(".env")
FORGE_API_KEY = env_values.get("FORGE_API_KEY", "")

# Fall back to standard dotenv loading if not found directly
if not FORGE_API_KEY:
    load_dotenv()
    FORGE_API_KEY = os.getenv("FORGE_API_KEY", "")

# Configuration
FORGE_API_URL = env_values.get(
    "FORGE_API_URL", os.getenv("FORGE_API_URL", "http://localhost:8000")
)

if not FORGE_API_KEY:
    print("Error: FORGE_API_KEY environment variable is not set.")
    print("Please set it to your Forge API key and try again.")
    sys.exit(1)


def chat_completion(messages, model="mock-only-gpt-3.5-turbo"):
    """Send a chat completion request to Forge"""
    url = f"{FORGE_API_URL}/chat/completions"
    headers = {"X-API-KEY": FORGE_API_KEY}
    data = {"model": model, "messages": messages, "temperature": 0.7}

    try:
        start_time = time.time()
        response = requests.post(url, json=data, headers=headers)
        end_time = time.time()

        if response.status_code == HTTPStatus.OK:
            result = response.json()
            print(f"Request completed in {end_time - start_time:.2f} seconds")
            return {
                "success": True,
                "response": result["choices"][0]["message"]["content"],
                "model": result["model"],
                "response_time": end_time - start_time,
            }
        else:
            return {
                "success": False,
                "error": f"API error: {response.status_code}",
                "details": response.text,
            }
    except Exception as e:
        return {"success": False, "error": "Request failed", "details": str(e)}


def simulate_conversation():
    """Simulate a conversation using the Forge API"""
    messages = []

    # Initial system message
    system_message = {
        "role": "system",
        "content": "You are a helpful and friendly AI assistant.",
    }
    messages.append(system_message)

    # First user message
    first_user_message = {
        "role": "user",
        "content": "Hello! Can you tell me what Forge is?",
    }
    messages.append(first_user_message)

    print("\n--- User: Hello! Can you tell me what Forge is?")
    result = chat_completion(messages)

    if result["success"]:
        print(f"\n--- AI ({result['model']}): {result['response']}")
        messages.append({"role": "assistant", "content": result["response"]})
    else:
        print(f"\nError: {result['error']}")
        print(f"Details: {result.get('details', 'No details available')}")
        return

    # Second user message
    second_user_message = {
        "role": "user",
        "content": "How can I use Forge with other frontend applications?",
    }
    messages.append(second_user_message)

    print("\n--- User: How can I use Forge with other frontend applications?")
    result = chat_completion(messages)

    if result["success"]:
        print(f"\n--- AI ({result['model']}): {result['response']}")
        messages.append({"role": "assistant", "content": result["response"]})
    else:
        print(f"\nError: {result['error']}")
        print(f"Details: {result.get('details', 'No details available')}")
        return

    # Try a different model if available
    third_user_message = {
        "role": "user",
        "content": "Can you summarize our conversation so far?",
    }
    messages.append(third_user_message)

    print("\n--- User: Can you summarize our conversation so far?")

    # Try with a different model if available
    alternative_model = "mock-only-gpt-4"  # Will fallback if not available
    result = chat_completion(messages, model=alternative_model)

    if result["success"]:
        print(f"\n--- AI ({result['model']}): {result['response']}")
    else:
        print(f"\nError: {result['error']}")
        print(f"Details: {result.get('details', 'No details available')}")


if __name__ == "__main__":
    print("🔄 Simulating a frontend application using Forge API")
    print(f"🔌 Connecting to Forge at {FORGE_API_URL}")
    print(f"🔑 Using Forge API Key: {FORGE_API_KEY[:8]}...")

    simulate_conversation()
