#!/usr/bin/env python3
"""
Test script for the mock provider.
This script sends requests to Forge using the mock provider to verify it works.
"""

import argparse
import http
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Load environment variables from project root
os.chdir(script_dir)
load_dotenv()

# Constants
API_KEY_PREFIX_LENGTH = 4
API_KEY_MIN_LENGTH = 8
TEST_OK = True
TEST_FAILED = False
HTTP_OK = http.HTTPStatus.OK  # 200


def test_mock_provider(
    forge_api_key: str | None = None, base_url: str = "http://localhost:8000"
) -> bool:
    """Run a test of the mock provider"""
    # Track overall test status
    all_tests_passed = True

    # If no API key is provided, check environment or use a mock key
    if not forge_api_key:
        # Try to get from environment
        forge_api_key = os.getenv("FORGE_API_KEY")

        # If still no key, use the standard test key
        if not forge_api_key:
            print("ℹ️ Using the standard test key: forge-test-mock-api-key")
            forge_api_key = "forge-test-mock-api-key"

        # CI testing fallback if needed
        elif forge_api_key and os.getenv("CI_TESTING"):
            print("🧪 CI Testing mode detected, using mock Forge API key")
            forge_api_key = "mock-forge-api-key-for-testing"

    print(
        f"🔑 Using API key: {forge_api_key[:API_KEY_PREFIX_LENGTH]}...{forge_api_key[-API_KEY_PREFIX_LENGTH:] if len(forge_api_key) > API_KEY_MIN_LENGTH else ''}"
    )

    headers = {
        "X-API-KEY": forge_api_key,
        "Content-Type": "application/json",
    }

    # First test connectivity to the server
    print("🔄 Testing server connectivity...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"📊 Server response: {response.status_code}")
        if response.status_code == HTTP_OK:
            print("✅ Server is running")
        else:
            print(f"⚠️ Server response: {response.text}")
    except Exception as e:
        print(f"❌ Failed to connect to server: {str(e)}")
        print(f"⚠️ Is the server running at {base_url}?")
        return TEST_FAILED

    # Test standard chat completion
    print("🧪 Testing chat completion with mock provider...")
    all_tests_passed = test_chat_completion(base_url, headers) and all_tests_passed

    # Test completion
    print("\n🧪 Testing text completion with mock provider...")
    all_tests_passed = test_text_completion(base_url, headers) and all_tests_passed

    # Test streaming
    print("\n🧪 Testing streaming with mock provider...")
    all_tests_passed = test_streaming(base_url, headers) and all_tests_passed

    # Test model listing to ensure mock models appear
    print("\n🧪 Testing models endpoint...")
    all_tests_passed = test_models(base_url, headers) and all_tests_passed

    # Test image generation
    print("\n🧪 Testing image generation with mock provider...")
    all_tests_passed = test_image_generation(base_url, headers) and all_tests_passed

    # Test image edits
    print("\n🧪 Testing image edits with mock provider...")
    all_tests_passed = test_image_edits(base_url, headers) and all_tests_passed

    if all_tests_passed:
        print("\n🎉 All mock provider tests completed successfully!")
    else:
        print("\n❌ Some tests failed.")

    return all_tests_passed


def test_chat_completion(base_url: str, headers: dict[str, str]) -> bool:
    """Test chat completion endpoint"""
    chat_data = {
        "model": "mock-only-gpt-4",
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions", headers=headers, json=chat_data
        )

        if response.status_code == HTTP_OK:
            result = response.json()
            print("✅ Chat completion successful!")
            print(f"Response: {result['choices'][0]['message']['content']}")
            return TEST_OK
        else:
            print(f"❌ Chat completion failed: {response.text}")
            return TEST_FAILED
    except Exception as e:
        print(f"❌ Error in chat completion: {str(e)}")
        return TEST_FAILED


def test_text_completion(base_url: str, headers: dict[str, str]) -> bool:
    """Test text completion endpoint"""
    completion_data = {
        "model": "mock-only-gpt-3.5-turbo",
        "prompt": "Tell me about Forge middleware",
    }

    try:
        response = requests.post(
            f"{base_url}/completions", headers=headers, json=completion_data
        )

        if response.status_code == HTTP_OK:
            result = response.json()
            print("✅ Text completion successful!")
            print(f"Response: {result['choices'][0]['text']}")
            return TEST_OK
        else:
            print(f"❌ Text completion failed: {response.text}")
            return TEST_FAILED
    except Exception as e:
        print(f"❌ Error in text completion: {str(e)}")
        return TEST_FAILED


def test_streaming(base_url: str, headers: dict[str, str]) -> bool:
    """Test streaming chat completion"""
    streaming_data = {
        "model": "mock-only-gpt-4",
        "messages": [
            {"role": "user", "content": "Explain how the mock provider works"}
        ],
        "stream": True,
    }

    try:
        with requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=streaming_data,
            stream=True,
        ) as response:
            if response.status_code == HTTP_OK:
                print("✅ Streaming started successfully!")
                print("Streaming response:")

                for response_line in response.iter_lines():
                    if response_line:
                        # Remove the "data: " prefix and parse JSON
                        decoded_line = response_line.decode("utf-8")
                        if (
                            decoded_line.startswith("data: ")
                            and decoded_line != "data: [DONE]"
                        ):
                            data = json.loads(decoded_line[6:])
                            if (
                                "choices" in data
                                and data["choices"]
                                and "delta" in data["choices"][0]
                            ):
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    print(content, end="", flush=True)

                print("\n✅ Streaming completed successfully!")
                return TEST_OK
            else:
                print(f"❌ Streaming failed: {response.text}")
                return TEST_FAILED
    except Exception as e:
        print(f"❌ Error in streaming: {str(e)}")
        return TEST_FAILED


def test_models(base_url: str, headers: dict[str, str]) -> bool:
    """Test models listing endpoint"""
    try:
        response = requests.get(f"{base_url}/models", headers=headers)

        if response.status_code == HTTP_OK:
            result = response.json()
            # Look for models with mock-only- prefix
            mock_models = [
                m for m in result["data"] if m["id"].startswith("mock-only-")
            ]

            if mock_models:
                print("✅ Mock-only models found in models endpoint!")
                print("Available mock-only models:")
                for model in mock_models:
                    print(f"  - {model['id']}")
                return TEST_OK
            else:
                print("⚠️ No mock-only models found in models endpoint.")
                print("🔍 Looking for models owned by 'mock' as fallback...")
                # Fallback to the old way for compatibility
                fallback_models = [m for m in result["data"] if m["owned_by"] == "mock"]
                if fallback_models:
                    print("✅ Models owned by 'mock' found!")
                    print("Available mock models (using owned_by):")
                    for model in fallback_models:
                        print(f"  - {model['id']}")
                    print("ℹ️ Note: These should be updated to use mock-only- prefix")
                    return TEST_OK
                return TEST_FAILED
        else:
            print(f"❌ Models endpoint failed: {response.text}")
            return TEST_FAILED
    except Exception as e:
        print(f"❌ Error accessing models endpoint: {str(e)}")
        return TEST_FAILED

def test_image_generation(base_url: str, headers: dict[str, str]) -> bool:
    """Test image generation endpoint"""
    image_data = {
        "model": "mock-only-dall-e-2",
        "prompt": "A beautiful sunset over a calm ocean",
    }

    try:
        response = requests.post(
            f"{base_url}/images/generations", headers=headers, json=image_data
        )

        if response.status_code == HTTP_OK:
            result = response.json()
            print("✅ Image generation successful!")
            print(f"Response: {result['data'][0]['url']}")
            return TEST_OK
        else:
            print(f"❌ Image generation failed: {response.text}")
            return TEST_FAILED
    except Exception as e:
        print(f"❌ Error in image generation: {str(e)}")
        return TEST_FAILED

def test_image_edits(base_url: str, headers: dict[str, str]) -> bool:
    """Test image edits endpoint"""
    image_data = {
        "model": "mock-only-dall-e-2",
        "prompt": "A beautiful sunset over a calm ocean",
    }

    try:
        response = requests.post(
            f"{base_url}/images/edits", headers=headers, json=image_data
        )

        if response.status_code == HTTP_OK:
            result = response.json()
            print("✅ Image edits successful!")
            print(f"Response: {result['data'][0]['url']}")
            return TEST_OK
        else:
            print(f"❌ Image edits failed: {response.text}")
            return TEST_FAILED
    except Exception as e:
        print(f"❌ Error in image edits: {str(e)}")
        return TEST_FAILED

def main():
    parser = argparse.ArgumentParser(description="Test the mock provider with Forge")
    parser.add_argument(
        "--api-key",
        "-k",
        help="Your Forge API key (optional, will use forge-test-mock-api-key if not provided)",
    )
    parser.add_argument(
        "--url",
        "-u",
        default="http://localhost:8000",
        help="Base URL for Forge API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging to see caching in action",
    )

    args = parser.parse_args()

    # If debug logging is enabled, set environment variable for the server to use
    if args.debug:
        os.environ["FORGE_DEBUG_LOGGING"] = "1"
        print("🐛 Debug logging enabled - you'll see cache usage in server logs")

    if test_mock_provider(args.api_key, args.url):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
