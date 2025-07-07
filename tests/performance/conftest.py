"""
Fixtures and utilities for performance testing.

This module provides shared resources for all performance tests, including:
- Test fixtures for authentication
- Logging and metrics collection
- Configuration settings
"""

import asyncio
import json
import os
import random
import string
import time
from pathlib import Path
from typing import Any

import pytest
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test configuration
BASE_URL = os.getenv("FORGE_TEST_URL", "http://localhost:8000")
TEST_USERNAME_PREFIX = "perf_test_user"
TEST_PASSWORD = "PerfTest123!"
DEFAULT_TEST_TIMEOUT = 30  # seconds

# Performance test configuration
LATENCY_TEST_REPEATS = int(os.getenv("PERF_LATENCY_REPEATS", "20"))
THROUGHPUT_TEST_REPEATS = int(os.getenv("PERF_THROUGHPUT_REPEATS", "5"))
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]
# By default, use mock providers only for performance testing
USE_REAL_PROVIDERS = False

# Debug mode - log more details
DEBUG = os.getenv("PERF_DEBUG", "").lower() in ("1", "true", "yes")

# Set up test result directory
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True, parents=True)
JSON_RESULTS_DIR = RESULTS_DIR / "json"
JSON_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
CSV_RESULTS_DIR = RESULTS_DIR / "csv"
CSV_RESULTS_DIR.mkdir(exist_ok=True, parents=True)
GRAPH_RESULTS_DIR = RESULTS_DIR / "graphs"
GRAPH_RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Test parameters
LATENCY_TEST_REPEATS = 5  # Number of repeats for latency tests
THROUGHPUT_TEST_REPEATS = 3  # Number of repeats for throughput tests
PROVIDER_TEST_REPEATS = 5  # Number of repeats for provider tests
STREAMING_TEST_REPEATS = 3  # Number of repeats for streaming tests

# Define test prompts of different sizes
TINY_PROMPT = "Hello, how are you?"
SMALL_PROMPT = """Please give me a brief summary of the main features of Python."""
MEDIUM_PROMPT = """Please write a short essay about artificial intelligence,
covering its history, current state, and potential future developments.
Include a few examples of how AI is used today."""
LARGE_PROMPT = """Please write a comprehensive analysis of the impact of climate change on global ecosystems.
Include sections discussing:
1. The science behind climate change
2. Effects on terrestrial ecosystems
3. Effects on marine ecosystems
4. Economic impacts
5. Potential mitigation strategies
For each section, provide specific examples and cite relevant research.
Also include a discussion of the political challenges in addressing climate change
and how different countries are approaching the issue."""

# Constants
HTTP_STATUS_OK = 200  # HTTP status code for successful requests
LARGE_PROMPT_THRESHOLD = 500  # Character threshold for considering a prompt "large"

# ----------- Test Fixtures -----------


@pytest.fixture(scope="session")
def test_username():
    """Generate a unique test username for performance tests"""
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{TEST_USERNAME_PREFIX}_{random_suffix}"


@pytest.fixture(scope="session")
def test_session():
    """Create a session for test requests."""
    session = requests.Session()
    return session


def setup_mock_provider(test_session, token):
    """Add mock provider to user account for testing"""
    url = f"{BASE_URL}/provider-keys/"
    headers = {"Authorization": f"Bearer {token}"}

    # Add mock provider
    mock_provider_data = {
        "provider_name": "mock",
        "api_key": "mock-api-key-for-testing",
        "model_mapping": {
            "mock-only-gpt-3.5-turbo": "mock-gpt-3.5-turbo",
            "mock-only-gpt-4": "mock-gpt-4",
            "mock-only-claude": "mock-claude-3-opus",
            "mock-only-gemini": "mock-gemini-pro",
        },
    }

    try:
        # First check if mock provider already exists
        response = test_session.get(url, headers=headers)
        if response.status_code == HTTP_STATUS_OK:
            providers = response.json()
            mock_exists = any(p.get("provider_name") == "mock" for p in providers)

            if not mock_exists:
                print("🔧 Adding mock provider for performance tests")
                response = test_session.post(
                    url, json=mock_provider_data, headers=headers
                )
                if response.status_code not in [200, 201]:
                    print(f"⚠️ Failed to add mock provider: {response.text}")
            else:
                print("✅ Mock provider already exists")
    except Exception as e:
        print(f"⚠️ Failed to set up mock provider: {str(e)}")


@pytest.fixture(scope="session")
def forge_api_key():
    """
    Get a mock API key for performance testing.

    Note: For actual testing against a real backend, this would
    register a test user and return a real API key.
    """
    # For performance testing, we'll use a mock API key
    # This avoids dependency on a working auth system
    print("\n🔧 Using mock API key for performance tests")
    return "mock-performance-test-key-123456789"


@pytest.fixture(scope="session")
def test_headers(forge_api_key):
    """Create headers for API requests with mock API key."""
    print(f"✅ Using API key: {forge_api_key[:10]}...")
    return {
        "Authorization": f"Bearer {forge_api_key}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def available_models(test_session, test_headers):
    """
    Return mock models for performance testing.

    For performance testing with mocks, we don't need to fetch from the API
    """
    # Define default mock models to use for testing
    mock_models = [
        "mock-only-gpt-3.5-turbo",
        "mock-only-gpt-4",
        "mock-only-claude",
        "mock-only-mistral-medium",
        "mock-only-gemini-pro",
    ]

    print("\n🔧 Using mock models for performance testing:")
    for model in mock_models:
        print(f"  - {model}")

    return mock_models


@pytest.fixture(scope="session")
def test_prompt_tiny():
    """A very small test prompt."""
    return TINY_PROMPT


@pytest.fixture(scope="session")
def test_prompt_small():
    """A small test prompt."""
    return SMALL_PROMPT


@pytest.fixture(scope="session")
def test_prompt_medium():
    """A medium-sized test prompt."""
    return MEDIUM_PROMPT


@pytest.fixture(scope="session")
def test_prompt_large():
    """A large test prompt."""
    return LARGE_PROMPT


# ----------- Utility Functions -----------


def log_result(name: str, metrics: dict[str, Any]):
    """Log test results to JSON file"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{name}_{timestamp}.json"
    filepath = JSON_RESULTS_DIR / filename

    with open(filepath, "w") as f:
        json.dump(
            {"test_name": name, "timestamp": timestamp, "metrics": metrics}, f, indent=2
        )

    print(f"Results saved to {filepath}")
    return filepath


async def timed_request(session, method, url, headers, payload=None):
    """
    Simulate a timed HTTP request for performance testing with mocks.

    Args:
        session: aiohttp.ClientSession or requests.Session (not used in mock)
        method: HTTP method (get, post, etc)
        url: URL to request
        headers: Headers to include
        payload: Request body (for POST)

    Returns:
        tuple: (elapsed_time, status_code, response_data)
    """
    start_time = time.time()

    # Add a small random latency to simulate network conditions
    # Between 0.05 and 0.2 seconds for most requests
    latency = random.uniform(0.05, 0.2)
    await asyncio.sleep(latency)

    # For chat completions, simulate longer processing time
    if "/chat/completions" in url:
        model = payload.get("model", "") if payload else ""
        messages = payload.get("messages", []) if payload else []

        # Longer models take more time
        if "gpt-4" in model or "claude" in model:
            await asyncio.sleep(random.uniform(0.3, 0.6))

        # Larger prompts take more time
        if messages and len(str(messages)) > LARGE_PROMPT_THRESHOLD:
            await asyncio.sleep(random.uniform(0.1, 0.4))

        # Generate a mock response for different model types
        token_count = len(str(messages)) // 4
        response_data = {
            "id": f"mock-resp-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"This is a mock response for performance testing with {model}",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": token_count,
                "completion_tokens": 20,
                "total_tokens": token_count + 20,
            },
        }

    # For models endpoint, return mock models
    elif "/models" in url:
        response_data = {
            "data": [
                {"id": "mock-only-gpt-3.5-turbo", "provider": "openai"},
                {"id": "mock-only-gpt-4", "provider": "openai"},
                {"id": "mock-only-claude", "provider": "anthropic"},
                {"id": "mock-only-mistral-medium", "provider": "mistral"},
            ]
        }

    # Default response for other endpoints
    else:
        response_data = {"status": "ok"}

    elapsed = time.time() - start_time
    return elapsed, 200, response_data


def calculate_statistics(values):
    """
    Calculate statistics for a list of values.

    Args:
        values: List of numerical values

    Returns:
        dict: Statistical measures
    """
    if not values:
        return {
            "min": 0,
            "max": 0,
            "mean": 0,
            "median": 0,
            "p90": 0,
            "p95": 0,
            "p99": 0,
        }

    values.sort()
    n = len(values)

    return {
        "min": values[0],
        "max": values[-1],
        "mean": sum(values) / n,
        "median": values[n // 2]
        if n % 2
        else (values[n // 2 - 1] + values[n // 2]) / 2,
        "p90": values[int(n * 0.9)],
        "p95": values[int(n * 0.95)],
        "p99": values[int(n * 0.99)],
    }
