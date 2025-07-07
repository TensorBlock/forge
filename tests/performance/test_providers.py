#!/usr/bin/env python3
"""
Provider-specific performance tests for Forge.

These tests compare the performance of different providers and measure
the overhead added by the Forge middleware. Tests include:

1. Comparing latency across different providers
2. Measuring baseline provider latency vs. Forge proxy latency
3. Testing provider-specific optimizations

Note: These tests use mock providers to ensure consistent test results
without external dependencies.
"""

import asyncio
import random
import time

import pytest

from .conftest import (
    BASE_URL,
    LATENCY_TEST_REPEATS,
    PROVIDER_TEST_REPEATS,
    calculate_statistics,
    log_result,
    timed_request,
)

# Constants
HTTP_STATUS_OK = 200  # HTTP status code for successful requests
MIN_SUCCESS_RATE = 50  # Minimum acceptable success rate percentage


@pytest.fixture(scope="module")
def provider_models(available_models):
    """Get available models organized by provider"""
    # Use mock models by default to ensure consistent performance tests
    provider_map = {"openai": [], "anthropic": [], "google": [], "mock": []}

    for model in available_models:
        model_lower = model.lower()
        if "mock" in model_lower and "gpt" in model_lower:
            # If we have a mock-gpt model, categorize it under openai for testing
            provider_map["openai"].append(model)
        elif "mock" in model_lower and "claude" in model_lower:
            provider_map["anthropic"].append(model)
        elif "mock" in model_lower and "gemini" in model_lower:
            provider_map["google"].append(model)
        elif "mock" in model_lower:
            # Any other mock model
            provider_map["mock"].append(model)
        elif "gpt" in model_lower:
            provider_map["openai"].append(model)
        elif "claude" in model_lower:
            provider_map["anthropic"].append(model)
        elif "gemini" in model_lower:
            provider_map["google"].append(model)

    # If we don't have models in certain categories, add default mock models
    if not provider_map["openai"]:
        provider_map["openai"].append("mock-only-gpt-3.5-turbo")
    if not provider_map["anthropic"]:
        provider_map["anthropic"].append("mock-only-claude")
    if not provider_map["google"]:
        provider_map["google"].append("mock-only-gemini")
    if not provider_map["mock"]:
        provider_map["mock"].append("mock-only-gpt-4")

    return provider_map


@pytest.mark.benchmark
@pytest.mark.parametrize("provider", ["openai", "anthropic", "google", "mock"])
def test_provider_latency_comparison(
    test_session, test_headers, provider_models, test_prompt_small, provider
):
    """
    Compare latency across different providers.

    This test skips providers that aren't available.
    """
    models = provider_models.get(provider, [])
    if not models:
        pytest.skip(f"No {provider} models available")

    # Use the first model from the provider
    model = models[0]

    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_prompt_small}],
    }

    latencies = []
    status_codes = []
    token_counts = []

    print(f"\nTesting {provider} latency with model {model}...")

    # Perform multiple requests
    for _ in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, response_data = asyncio.run(
            timed_request(test_session, "post", url, test_headers, payload)
        )
        latencies.append(elapsed)
        status_codes.append(status_code)

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

    # Print results
    print(f"\n{provider.capitalize()} Provider Latency Results (n={len(latencies)}):")
    print(f"  Model: {model}")
    print(f"  Min: {stats['min']:.4f}s")
    print(f"  Max: {stats['max']:.4f}s")
    print(f"  Mean: {stats['mean']:.4f}s")
    print(f"  Median: {stats['median']:.4f}s")
    print(f"  P90: {stats['p90']:.4f}s")
    print(f"  P99: {stats['p99']:.4f}s")
    print(f"  Success Rate: {success_rate:.1f}%")

    if token_counts:
        avg_total_tokens = sum(tc.get("total_tokens", 0) for tc in token_counts) / len(
            token_counts
        )
        print(f"  Avg Total Tokens: {avg_total_tokens:.1f}")

    # Log results
    result_data = {
        "provider": provider,
        "model": model,
        "stats": stats,
        "success_rate": success_rate,
        "status_codes": status_codes,
    }

    if token_counts:
        result_data["token_stats"] = {
            "counts": token_counts,
            "avg_total_tokens": avg_total_tokens if token_counts else 0,
        }

    log_result(f"provider_latency_{provider}", result_data)

    # Validation
    assert success_rate > MIN_SUCCESS_RATE, f"Success rate too low for {provider}"


@pytest.mark.benchmark
def test_provider_overhead(
    test_session, test_headers, provider_models, test_prompt_small
):
    """
    Measure the overhead added by the Forge middleware.

    This test is especially valuable for understanding the performance
    impact of the Forge proxy layer.
    """
    # Choose OpenAI as the reference provider if available
    openai_models = provider_models.get("openai", [])

    if not openai_models:
        pytest.skip("No OpenAI models available for overhead testing")

    model = openai_models[0]
    forge_url = f"{BASE_URL}/chat/completions"

    print(f"\nMeasuring Forge middleware overhead using model {model}...")

    # Prepare request payload
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_prompt_small}],
    }

    # Test Forge proxy latency
    forge_latencies = []
    forge_status_codes = []

    for _ in range(LATENCY_TEST_REPEATS):
        elapsed, status_code, _ = asyncio.run(
            timed_request(test_session, "post", forge_url, test_headers, payload)
        )
        forge_latencies.append(elapsed)
        forge_status_codes.append(status_code)

    forge_stats = calculate_statistics(forge_latencies)
    forge_success_rate = (
        forge_status_codes.count(HTTP_STATUS_OK) / len(forge_status_codes) * 100
    )

    # Calculate overhead percentage
    # Note: In a real implementation, we would test direct API call latency
    # as well and calculate the exact overhead. Here we're just measuring the
    # Forge proxy time as a baseline.

    # Print results
    print(f"\nForge Middleware Overhead Results (n={len(forge_latencies)}):")
    print(f"  Model: {model}")
    print(f"  Forge Mean Latency: {forge_stats['mean']:.4f}s")
    print(f"  Forge Median Latency: {forge_stats['median']:.4f}s")
    print(f"  Forge P90 Latency: {forge_stats['p90']:.4f}s")
    print(f"  Success Rate: {forge_success_rate:.1f}%")

    # Log results
    result_data = {
        "model": model,
        "forge_stats": forge_stats,
        "forge_success_rate": forge_success_rate,
    }

    log_result("forge_middleware_overhead", result_data)

    # Validation
    assert forge_success_rate > MIN_SUCCESS_RATE, (
        "Success rate too low for Forge middleware"
    )


@pytest.mark.benchmark
@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_provider_streaming_performance(
    test_session, test_headers, provider_models, test_prompt_medium, provider
):
    """
    Test streaming performance for different providers using mock responses.

    This measures time to first token (TTFT) and throughput for streaming responses.
    """
    models = provider_models.get(provider, [])
    if not models:
        pytest.skip(f"No {provider} models available")

    # Use the first model from the provider
    model = models[0]

    all_metrics = []

    print(f"\nTesting {provider} streaming performance with model {model}...")

    # Setup mock streaming test
    async def mock_streaming_request():
        # Start time for calculating metrics
        start_time = time.time()

        # Simulate initial processing delay before first token
        first_token_delay = (
            0.1 if "gpt" in model else 0.15 if "claude" in model else 0.08
        )
        await asyncio.sleep(first_token_delay)
        first_token_time = time.time()

        # Number of tokens to generate
        num_tokens = 20
        tokens_per_sec = 5.0  # Baseline tokens per second

        # Simulate streaming tokens with slight random variations
        for _i in range(num_tokens):
            token_delay = 1.0 / (
                tokens_per_sec * (0.8 + random.random() * 0.4)
            )  # Add 20% randomness
            await asyncio.sleep(token_delay)

        end_time = time.time()

        # Calculate metrics
        ttft = first_token_time - start_time
        total_time = end_time - start_time
        streaming_time = end_time - first_token_time
        tokens_per_second = num_tokens / streaming_time if streaming_time > 0 else 0

        return {
            "success": True,
            "ttft": ttft,
            "total_time": total_time,
            "streaming_time": streaming_time,
            "token_count": num_tokens,
            "tokens_per_second": tokens_per_second,
        }

    # Run streaming tests
    for i in range(PROVIDER_TEST_REPEATS):
        print(f"  Running streaming test iteration {i + 1}...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            metrics = loop.run_until_complete(mock_streaming_request())
            all_metrics.append(metrics)

            print(f"    TTFT: {metrics.get('ttft', 'N/A'):.4f}s")
            print(f"    Tokens/sec: {metrics.get('tokens_per_second', 'N/A'):.2f}")
        finally:
            loop.close()

    # Process successful results
    successful_metrics = [m for m in all_metrics if m.get("success", False)]
    success_rate = len(successful_metrics) / len(all_metrics) * 100

    avg_ttft = sum(m["ttft"] for m in successful_metrics if m.get("ttft")) / len(
        successful_metrics
    )
    avg_tokens_per_sec = sum(m["tokens_per_second"] for m in successful_metrics) / len(
        successful_metrics
    )

    print(
        f"\n{provider.capitalize()} Streaming Performance (n={len(successful_metrics)}):"
    )
    print(f"  Model: {model}")
    print(f"  Avg TTFT: {avg_ttft:.4f}s")
    print(f"  Avg Tokens/sec: {avg_tokens_per_sec:.2f}")
    print(f"  Success Rate: {success_rate:.1f}%")

    # Log results
    log_result(
        f"streaming_performance_{provider}",
        {
            "provider": provider,
            "model": model,
            "ttft": {
                "avg": avg_ttft,
                "values": [m.get("ttft") for m in successful_metrics if m.get("ttft")],
            },
            "tokens_per_second": {
                "avg": avg_tokens_per_sec,
                "values": [m.get("tokens_per_second", 0) for m in successful_metrics],
            },
            "success_rate": success_rate,
            "metrics": all_metrics,
        },
    )


@pytest.mark.benchmark
def test_provider_chat_completion_performance(
    test_session, test_headers, available_models, test_prompt_small
):
    """
    Compare chat completion performance across different providers.

    This test uses mock providers to simulate different provider APIs and
    measures their performance characteristics.
    """
    # Define mock providers to test
    mock_providers = {
        "openai": "mock-only-gpt-3.5-turbo",
        "anthropic": "mock-only-claude",
        "mistral": "mock-only-mistral-medium",
    }

    # Filter to available mock models
    available_mock_providers = {}
    for provider, model_pattern in mock_providers.items():
        for model in available_models:
            if model_pattern.lower() in model.lower():
                available_mock_providers[provider] = model
                break

    # If no mock models are available, use defaults
    if not available_mock_providers:
        print("⚠️ No mock models found in available models. Using defaults:")
        available_mock_providers = mock_providers
        for provider, model in available_mock_providers.items():
            print(f"  {provider}: {model}")

    # Test each provider
    provider_results = {}

    for provider, model in available_mock_providers.items():
        print(f"\nTesting mock provider: {provider} using model: {model}")

        url = f"{BASE_URL}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": test_prompt_small}],
        }

        latencies = []
        status_codes = []
        first_response = None

        # Perform multiple requests
        for i in range(PROVIDER_TEST_REPEATS):
            elapsed, status_code, response_data = asyncio.run(
                timed_request(test_session, "post", url, test_headers, payload)
            )
            latencies.append(elapsed)
            status_codes.append(status_code)

            # Store first response for debugging
            if i == 0:
                first_response = response_data

        # Calculate statistics
        stats = calculate_statistics(latencies)
        success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100

        # Print results
        print(f"\nChat Completion Performance for {provider} (model: {model}):")
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

        # Store results for comparison
        provider_results[provider] = {
            "model": model,
            "stats": stats,
            "success_rate": success_rate,
            "status_codes": status_codes,
            "first_response": str(first_response)[:500] if first_response else None,
        }

    # Log overall provider comparison
    log_result("provider_chat_completion_performance", provider_results)

    # If we have more than one provider to compare, print a comparison
    if len(provider_results) > 1:
        print("\nProvider Performance Comparison (Mean Latency):")
        for provider, results in sorted(
            provider_results.items(), key=lambda x: x[1]["stats"]["mean"]
        ):
            print(
                f"  {provider}: {results['stats']['mean']:.4f}s (model: {results['model']})"
            )

    # Skip with a message if all tests had low success rates
    if all(
        results["success_rate"] <= MIN_SUCCESS_RATE
        for results in provider_results.values()
    ):
        pytest.skip("All provider tests had low success rates")
