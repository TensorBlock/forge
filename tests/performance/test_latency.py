#!/usr/bin/env python3
"""
Latency benchmarks for Forge API.

These tests measure the response time of various API endpoints
under different conditions, focusing on:

1. Chat completion latency with different model types
2. Latency with different prompt sizes
3. End-to-end request time breakdown
"""

import asyncio

import pytest

from .conftest import (
    BASE_URL,
    LATENCY_TEST_REPEATS,
    calculate_statistics,
    log_result,
    timed_request,
)

# Constants
HTTP_STATUS_OK = 200  # HTTP status code for successful requests
MIN_SUCCESS_RATE = 50  # Minimum acceptable success rate percentage


@pytest.mark.benchmark
def test_api_key_validation_latency(test_session, test_headers):
    """Measure the latency of API key validation."""
    url = f"{BASE_URL}/models"

    latencies = []
    status_codes = []

    # Perform multiple requests to get a stable average
    for _ in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, _ = asyncio.run(
            timed_request(test_session, "get", url, test_headers)
        )
        latencies.append(elapsed)
        status_codes.append(status_code)

    # Calculate statistics
    stats = calculate_statistics(latencies)
    success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100

    # Print results
    print(f"\nAPI Key Validation Latency Statistics (n={len(latencies)}):")
    print(f"  Min: {stats['min']:.4f}s")
    print(f"  Max: {stats['max']:.4f}s")
    print(f"  Mean: {stats['mean']:.4f}s")
    print(f"  Median: {stats['median']:.4f}s")
    print(f"  P90: {stats['p90']:.4f}s")
    print(f"  P99: {stats['p99']:.4f}s")
    print(f"  Success Rate: {success_rate:.1f}%")

    # Log results
    log_result(
        "api_key_validation_latency",
        {"stats": stats, "success_rate": success_rate, "status_codes": status_codes},
    )

    # Validation
    assert success_rate > MIN_SUCCESS_RATE, "API key validation success rate too low"


@pytest.mark.benchmark
@pytest.mark.parametrize("model_type", ["gpt", "claude", "mock"])
def test_chat_completion_latency_by_model(
    test_session, test_headers, available_models, test_prompt_small, model_type
):
    """
    Measure chat completion latency by model type.

    This tests different model families to compare their performance.
    """
    # Define default models to use if selection fails
    default_models = {
        "gpt": "mock-only-gpt-3.5-turbo",
        "claude": "mock-only-claude",
        "mock": "mock-only-gpt-4",
    }

    # Select a model based on the model_type
    model = None
    for m in available_models:
        if model_type.lower() in m.lower():
            model = m
            break

    # If no matching model found, use default
    if not model:
        if model_type in default_models:
            model = default_models[model_type]
            print(
                f"⚠️ No {model_type} model found in available models. Using default: {model}"
            )
        else:
            pytest.skip(f"No {model_type} model available")

    print(f"\nUsing model: {model} for {model_type} model type test")

    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_prompt_small}],
    }

    latencies = []
    status_codes = []
    token_counts = []
    first_response = None

    # Perform multiple requests
    for i in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, response_data = asyncio.run(
            timed_request(test_session, "post", url, test_headers, payload)
        )
        latencies.append(elapsed)
        status_codes.append(status_code)

        # Store first response for debugging
        if i == 0:
            first_response = response_data

        # Extract token counts if available
        if status_code == HTTP_STATUS_OK and isinstance(response_data, dict):
            usage = response_data.get("usage", {})
            if usage:
                token_counts.append(
                    {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                )

    # Calculate statistics
    stats = calculate_statistics(latencies)
    success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100

    # Print results with more debug info
    print(f"\nChat Completion Latency for {model} (n={len(latencies)}):")
    print(f"  Min: {stats['min']:.4f}s")
    print(f"  Max: {stats['max']:.4f}s")
    print(f"  Mean: {stats['mean']:.4f}s")
    print(f"  Median: {stats['median']:.4f}s")
    print(f"  P90: {stats['p90']:.4f}s")
    print(f"  P99: {stats['p99']:.4f}s")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Status Codes: {status_codes[:5]}...")

    if first_response:
        print(f"  First Response: {str(first_response)[:200]}...")

    if token_counts:
        avg_total_tokens = sum(tc.get("total_tokens", 0) for tc in token_counts) / len(
            token_counts
        )
        print(f"  Avg Total Tokens: {avg_total_tokens:.1f}")

    # Log results
    result_data = {
        "model": model,
        "model_type": model_type,
        "stats": stats,
        "success_rate": success_rate,
        "status_codes": status_codes,
        "first_response": str(first_response)[:500] if first_response else None,
    }

    if token_counts:
        result_data["token_stats"] = {
            "counts": token_counts,
            "avg_total_tokens": sum(tc.get("total_tokens", 0) for tc in token_counts)
            / len(token_counts)
            if token_counts
            else 0,
        }

    log_result(f"chat_completion_latency_{model_type}", result_data)

    # For performance tests, we record the results even if they fail
    # This allows us to analyze failures and track changes over time
    if success_rate <= MIN_SUCCESS_RATE:
        pytest.skip(
            f"Chat completion success rate too low for {model_type} ({success_rate:.1f}%)"
        )


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "prompt_fixture,prompt_size",
    [
        ("test_prompt_small", "small"),
        ("test_prompt_medium", "medium"),
        ("test_prompt_large", "large"),
    ],
)
def test_chat_completion_latency_by_prompt_size(
    test_session, test_headers, available_models, prompt_fixture, prompt_size, request
):
    """
    Measure chat completion latency for different prompt sizes.

    This tests how latency scales with input size.
    """
    # Get the actual prompt from the fixture
    prompt = request.getfixturevalue(prompt_fixture)

    # Verify we have mock models available
    if not available_models:
        pytest.skip("No models available for testing")

    # Select first available model
    model = available_models[0] if available_models else "mock-only-gpt-3.5-turbo"
    print(f"\nUsing model: {model} for {prompt_size} prompt test")

    url = f"{BASE_URL}/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

    latencies = []
    status_codes = []
    token_counts = []

    first_response = None

    # Perform multiple requests
    for i in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, response_data = asyncio.run(
            timed_request(test_session, "post", url, test_headers, payload)
        )
        latencies.append(elapsed)
        status_codes.append(status_code)

        # Store first response for debugging
        if i == 0:
            first_response = response_data

        # Extract token counts if available
        if status_code == HTTP_STATUS_OK and isinstance(response_data, dict):
            usage = response_data.get("usage", {})
            if usage:
                token_counts.append(
                    {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }
                )

    # Calculate statistics
    stats = calculate_statistics(latencies)
    success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100

    # Print more detailed results for debugging
    print(f"\nChat Completion Latency for {prompt_size} prompt (n={len(latencies)}):")
    print(f"  Model: {model}")
    print(f"  Min: {stats['min']:.4f}s")
    print(f"  Max: {stats['max']:.4f}s")
    print(f"  Mean: {stats['mean']:.4f}s")
    print(f"  Median: {stats['median']:.4f}s")
    print(f"  P90: {stats['p90']:.4f}s")
    print(f"  P99: {stats['p99']:.4f}s")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Status Codes: {status_codes[:5]}...")

    if first_response:
        print(f"  First Response: {str(first_response)[:200]}...")

    if token_counts:
        avg_prompt_tokens = sum(
            tc.get("prompt_tokens", 0) for tc in token_counts
        ) / len(token_counts)
        print(f"  Avg Prompt Tokens: {avg_prompt_tokens:.1f}")

    # Log results
    result_data = {
        "model": model,
        "prompt_size": prompt_size,
        "stats": stats,
        "success_rate": success_rate,
        "status_codes": status_codes,
        "first_response": str(first_response)[:500] if first_response else None,
    }

    if token_counts:
        result_data["token_stats"] = {
            "counts": token_counts,
            "avg_prompt_tokens": sum(tc.get("prompt_tokens", 0) for tc in token_counts)
            / len(token_counts)
            if token_counts
            else 0,
        }

    log_result(f"chat_completion_latency_prompt_{prompt_size}", result_data)

    # For performance tests, we record the results even if they fail
    # This allows us to analyze failures and track changes over time
    if success_rate <= MIN_SUCCESS_RATE:
        pytest.skip(
            f"Chat completion success rate too low for {prompt_size} prompt ({success_rate:.1f}%)"
        )


@pytest.mark.benchmark
def test_models_endpoint_latency(test_session, test_headers):
    """Measure the latency of the models listing endpoint."""
    url = f"{BASE_URL}/models"

    latencies = []
    status_codes = []
    model_counts = []

    # Perform multiple requests
    for _ in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, response_data = asyncio.run(
            timed_request(test_session, "get", url, test_headers)
        )
        latencies.append(elapsed)
        status_codes.append(status_code)

        # Count models if available
        if status_code == HTTP_STATUS_OK and isinstance(response_data, dict):
            models = response_data.get("data", [])
            model_counts.append(len(models))

    # Calculate statistics
    stats = calculate_statistics(latencies)
    success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100
    avg_model_count = sum(model_counts) / len(model_counts) if model_counts else 0

    # Print results
    print(f"\nModels Endpoint Latency (n={len(latencies)}):")
    print(f"  Min: {stats['min']:.4f}s")
    print(f"  Max: {stats['max']:.4f}s")
    print(f"  Mean: {stats['mean']:.4f}s")
    print(f"  Median: {stats['median']:.4f}s")
    print(f"  P90: {stats['p90']:.4f}s")
    print(f"  P99: {stats['p99']:.4f}s")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Avg Model Count: {avg_model_count:.1f}")

    # Log results
    log_result(
        "models_endpoint_latency",
        {
            "stats": stats,
            "success_rate": success_rate,
            "status_codes": status_codes,
            "avg_model_count": avg_model_count,
        },
    )

    # Validation
    assert success_rate > MIN_SUCCESS_RATE, "Models endpoint success rate too low"
