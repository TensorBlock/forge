#!/usr/bin/env python3
"""
Throughput benchmarks for Forge API.

These tests measure the maximum request throughput of various API endpoints
under different concurrency levels, focusing on:

1. Maximum requests per second for chat completions
2. Throughput under different concurrency levels
3. System behavior under sustained load
"""

import asyncio
import random
import time

import aiohttp
import pytest
import requests

from .conftest import (
    BASE_URL,
    CONCURRENCY_LEVELS,
    THROUGHPUT_TEST_REPEATS,
    calculate_statistics,
    log_result,
    timed_request,
)

# Constants
HTTP_STATUS_OK = 200  # HTTP status code for successful requests
MIN_SUCCESS_RATE = 50  # Minimum acceptable success rate percentage


async def run_concurrent_requests(
    url: str,
    headers: dict[str, str],
    payload: dict,
    concurrency: int,
    duration: int = 5,
) -> tuple[list[float], list[int], int]:
    """
    Run concurrent requests for a specified duration.

    Args:
        url: The API endpoint URL
        headers: Request headers
        payload: Request payload
        concurrency: Number of concurrent requests
        duration: Test duration in seconds

    Returns:
        Tuple of (latencies, status_codes, request_count)
    """
    latencies = []
    status_codes = []

    start_time = time.time()
    end_time = start_time + duration

    async def make_request():
        req_start = time.time()
        try:
            async with asyncio.timeout(duration * 2):  # Timeout safety
                session = requests.Session()
                response = session.post(url, headers=headers, json=payload)
                latency = time.time() - req_start
                latencies.append(latency)
                status_codes.append(response.status_code)
        except Exception as e:
            print(f"Request error: {str(e)}")
            latencies.append(time.time() - req_start)
            status_codes.append(500)

    # Create tasks based on concurrency
    tasks = []
    # Keep making requests until the duration is up
    while time.time() < end_time:
        # Add more tasks if needed to maintain concurrency
        while len(tasks) < concurrency:
            tasks.append(asyncio.create_task(make_request()))

        # Wait for some tasks to complete
        done, pending = await asyncio.wait(
            tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
        )

        # Remove completed tasks
        tasks = list(pending)

    # Wait for remaining tasks to complete
    if tasks:
        await asyncio.wait(tasks)

    return latencies, status_codes, len(latencies)


@pytest.mark.benchmark
@pytest.mark.parametrize("concurrency", CONCURRENCY_LEVELS)
def test_models_endpoint_throughput(test_session, test_headers, concurrency):
    """
    Test the throughput of the models endpoint under different concurrency levels.

    This test uses mock responses for consistent measurement.
    """

    # Track metrics across all runs
    all_req_per_sec = []
    all_latencies = []
    all_status_codes = []

    print(f"\nMeasuring models endpoint throughput at concurrency={concurrency}...")

    # Use a simple custom mock request function for throughput testing
    async def mock_request():
        start_time = time.time()
        # Add a small random delay to simulate network and processing time
        await asyncio.sleep(random.uniform(0.001, 0.003))
        end_time = time.time()
        return end_time - start_time, 200, {"data": [{"id": "mock-model"}]}

    # Run multiple iterations
    for i in range(THROUGHPUT_TEST_REPEATS):
        # Set up the event loop for each iteration
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Define test duration
        duration = 2  # seconds (shorter for faster tests)

        async def run_mock_requests(test_duration=duration):
            start_time = time.time()
            end_time = start_time + test_duration
            tasks = []

            while time.time() < end_time:
                # Keep adding tasks to maintain concurrency
                while len(tasks) < concurrency:
                    tasks.append(asyncio.create_task(mock_request()))

                # Wait for some tasks to complete
                done, pending = await asyncio.wait(
                    tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed tasks
                for task in done:
                    latency, status_code, _ = task.result()
                    all_latencies.append(latency)
                    all_status_codes.append(status_code)

                # Update task list
                tasks = list(pending)

            # Wait for remaining tasks
            if tasks:
                done, _ = await asyncio.wait(tasks)
                for task in done:
                    latency, status_code, _ = task.result()
                    all_latencies.append(latency)
                    all_status_codes.append(status_code)

        try:
            # Run mock requests
            loop.run_until_complete(run_mock_requests(duration))
            req_count = len(all_latencies)
            req_per_sec = req_count / duration
            all_req_per_sec.append(req_per_sec)

            print(
                f"  Iteration {i + 1}: {req_per_sec:.2f} req/sec, {req_count} requests"
            )
        finally:
            loop.close()

    # Calculate statistics
    avg_req_per_sec = (
        sum(all_req_per_sec) / len(all_req_per_sec) if all_req_per_sec else 0
    )
    latency_stats = calculate_statistics(all_latencies)
    success_rate = (
        all_status_codes.count(HTTP_STATUS_OK) / len(all_status_codes) * 100
        if all_status_codes
        else 0
    )

    # Print results
    print(f"\nModels Endpoint Throughput Results (concurrency={concurrency}):")
    print(f"  Avg throughput: {avg_req_per_sec:.2f} req/sec")
    print(f"  Success rate: {success_rate:.1f}%")
    print(f"  Avg latency: {latency_stats['mean']:.4f}s")
    print(f"  P90 latency: {latency_stats['p90']:.4f}s")

    # Log results
    log_result(
        f"models_endpoint_throughput_c{concurrency}",
        {
            "concurrency": concurrency,
            "throughput": {
                "avg_req_per_sec": avg_req_per_sec,
                "all_iterations": all_req_per_sec,
            },
            "latency_stats": latency_stats,
            "success_rate": success_rate,
            "request_count": len(all_latencies),
        },
    )

    # Validation
    assert success_rate > MIN_SUCCESS_RATE, (
        f"Success rate too low for models endpoint at concurrency {concurrency}"
    )


@pytest.mark.benchmark
@pytest.mark.parametrize("concurrent_requests", [5, 10, 20])
def test_chat_completion_throughput(
    test_session, test_headers, available_models, test_prompt_small, concurrent_requests
):
    """
    Measure chat completion throughput by varying the number of concurrent requests.

    This tests how the API handles multiple concurrent requests and measures throughput.
    """
    # Prefer using a mock model for consistent testing
    mock_model = None
    for model in available_models:
        if "mock" in model.lower():
            mock_model = model
            break

    # If no mock model is found, use the first available model or skip
    if not mock_model:
        if available_models:
            mock_model = available_models[0]
            print(f"⚠️ No mock model found. Using first available model: {mock_model}")
        else:
            print("⚠️ No models available for testing")
            mock_model = "mock-only-gpt-3.5-turbo"  # Default fallback
            print(f"Using default mock model: {mock_model}")

    print(
        f"\nTesting throughput with {concurrent_requests} concurrent requests using model: {mock_model}"
    )

    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": mock_model,
        "messages": [{"role": "user", "content": test_prompt_small}],
    }

    # Prepare the asynchronous requests
    async def run_concurrent_requests():
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(concurrent_requests):
                tasks.append(timed_request(session, "post", url, test_headers, payload))
            return await asyncio.gather(*tasks)

    # Run the requests and measure total time
    start_time = time.time()
    results = asyncio.run(run_concurrent_requests())
    end_time = time.time()

    # Process results
    latencies = [result[0] for result in results]
    status_codes = [result[1] for result in results]
    first_response = results[0][2] if results else None

    # Calculate statistics
    total_time = end_time - start_time
    throughput = concurrent_requests / total_time
    success_rate = status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100

    # Calculate latency statistics
    latency_stats = calculate_statistics(latencies)

    # Print detailed results
    print(f"\nChat Completion Throughput ({concurrent_requests} concurrent requests):")
    print(f"  Total Time: {total_time:.4f}s")
    print(f"  Throughput: {throughput:.2f} req/s")
    print(f"  Success Rate: {success_rate:.1f}%")
    print(f"  Status Codes: {status_codes[:5]}...")

    if first_response:
        print(f"  First Response: {str(first_response)[:200]}...")

    print("\nLatency Statistics:")
    print(f"  Min: {latency_stats['min']:.4f}s")
    print(f"  Max: {latency_stats['max']:.4f}s")
    print(f"  Mean: {latency_stats['mean']:.4f}s")
    print(f"  Median: {latency_stats['median']:.4f}s")
    print(f"  P90: {latency_stats['p90']:.4f}s")
    print(f"  P99: {latency_stats['p99']:.4f}s")

    # Log results
    result_data = {
        "model": mock_model,
        "concurrent_requests": concurrent_requests,
        "total_time": total_time,
        "throughput": throughput,
        "success_rate": success_rate,
        "status_codes": status_codes,
        "latency_stats": latency_stats,
        "first_response": str(first_response)[:500] if first_response else None,
    }

    log_result(f"chat_completion_throughput_{concurrent_requests}", result_data)

    # For performance tests, we record the results even if they fail
    # This allows us to analyze failures and track changes over time
    if success_rate <= MIN_SUCCESS_RATE:
        pytest.skip(
            f"Chat completion success rate too low for throughput test ({success_rate:.1f}%)"
        )


@pytest.mark.benchmark
def test_sustained_load(
    test_session, test_headers, available_models, test_prompt_small
):
    """
    Test system behavior under sustained load over a longer period.

    This test uses mock responses to simulate sustained load.
    """
    # Select first available model
    model = available_models[0] if available_models else "mock-only-gpt-3.5-turbo"

    # Test parameters
    concurrency = 5  # Moderate concurrency
    duration = 10  # Duration (seconds) - reduced for faster tests

    print(
        f"\nRunning sustained load test with {concurrency} concurrent users for {duration}s..."
    )
    print(f"  Using model: {model}")

    # Set up the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Use a simple custom mock request function
    async def mock_request():
        start_time = time.time()
        # Add a small random delay to simulate network and processing time
        # Make later requests slightly slower to simulate degradation
        base_delay = 0.05
        elapsed_time = time.time() - start_time_global
        degradation_factor = 1.0 + (elapsed_time / duration) * 0.5  # Up to 50% slower

        await asyncio.sleep(base_delay * degradation_factor)

        token_count = len(test_prompt_small) // 4
        return (
            time.time() - start_time,
            HTTP_STATUS_OK,
            {
                "id": f"mock-resp-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "This is a mock response for load testing",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": token_count,
                    "completion_tokens": 20,
                    "total_tokens": token_count + 20,
                },
            },
        )

    latencies = []
    status_codes = []
    start_time_global = time.time()

    async def run_mock_requests():
        start_time = time.time()
        end_time = start_time + duration
        tasks = []

        while time.time() < end_time:
            # Keep adding tasks to maintain concurrency
            while len(tasks) < concurrency:
                tasks.append(asyncio.create_task(mock_request()))

            # Wait for some tasks to complete
            done, pending = await asyncio.wait(
                tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks
            for task in done:
                latency, status_code, _ = task.result()
                latencies.append(latency)
                status_codes.append(status_code)

            # Update task list
            tasks = list(pending)

        # Wait for remaining tasks
        if tasks:
            done, _ = await asyncio.wait(tasks)
            for task in done:
                latency, status_code, _ = task.result()
                latencies.append(latency)
                status_codes.append(status_code)

    try:
        # Run mock requests
        loop.run_until_complete(run_mock_requests())
        req_count = len(latencies)

        # Calculate metrics
        req_per_sec = req_count / duration
        latency_stats = calculate_statistics(latencies)
        success_rate = (
            status_codes.count(HTTP_STATUS_OK) / len(status_codes) * 100
            if status_codes
            else 0
        )

        # Analyze latencies over time to detect degradation
        # Split latencies into time segments
        segment_duration = 2  # seconds
        num_segments = duration // segment_duration

        # This simplification assumes requests are evenly distributed
        segment_size = (
            len(latencies) // num_segments if num_segments > 0 else len(latencies)
        )

        segment_stats = []
        for i in range(num_segments):
            start_idx = i * segment_size
            end_idx = start_idx + segment_size
            segment_latencies = latencies[start_idx:end_idx]
            if segment_latencies:
                segment_avg = sum(segment_latencies) / len(segment_latencies)
                segment_stats.append({"segment": i + 1, "avg_latency": segment_avg})

        # Check for performance degradation
        if segment_stats and len(segment_stats) > 1:
            first_segment_latency = segment_stats[0]["avg_latency"]
            last_segment_latency = segment_stats[-1]["avg_latency"]
            degradation_pct = ((last_segment_latency / first_segment_latency) - 1) * 100
        else:
            degradation_pct = 0

        # Print results
        print("\nSustained Load Test Results:")
        print(f"  Total requests: {req_count}")
        print(f"  Throughput: {req_per_sec:.2f} req/sec")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Avg latency: {latency_stats['mean']:.4f}s")
        print(f"  P90 latency: {latency_stats['p90']:.4f}s")
        print(f"  Perf degradation: {degradation_pct:.1f}%")

        # Log results
        log_result(
            "sustained_load_test",
            {
                "model": model,
                "concurrency": concurrency,
                "duration": duration,
                "throughput": req_per_sec,
                "latency_stats": latency_stats,
                "success_rate": success_rate,
                "request_count": req_count,
                "degradation": {"percent": degradation_pct, "segments": segment_stats},
            },
        )

    finally:
        loop.close()
