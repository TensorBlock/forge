#!/usr/bin/env python3
"""
Compare performance of synchronous vs. asynchronous cache implementations.

This script calls both the regular and async versions of the /models endpoint
and measures the performance difference.
"""

import asyncio
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import aiohttp
import requests

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to the project root directory
os.chdir(script_dir)

# Ensure DEBUG_CACHE is enabled to see cache operations
os.environ["DEBUG_CACHE"] = "true"


# Constants
DEFAULT_URL = "http://localhost:8000"
API_KEY = os.getenv("FORGE_API_KEY", "forge-api-key")
TEST_ITERATIONS = 5


async def test_async_endpoint(
    session: aiohttp.ClientSession, endpoint: str
) -> dict[str, Any]:
    """Test an async endpoint and return timing information"""
    url = f"{DEFAULT_URL}/{endpoint}"
    headers = {"X-API-KEY": API_KEY}

    # First call (expected cache miss)
    start_time = time.time()
    async with session.get(url, headers=headers) as response:
        await response.json()
    first_time = time.time() - start_time

    # Subsequent calls (expected cache hits)
    times = []
    for _ in range(TEST_ITERATIONS - 1):
        start_time = time.time()
        async with session.get(url, headers=headers) as response:
            await response.json()
        elapsed = time.time() - start_time
        times.append(elapsed)

    # Calculate average and other stats
    avg_time = statistics.mean(times) if times else 0

    return {
        "first_call": first_time,
        "avg_subsequent": avg_time,
        "all_times": [first_time] + times,
        "speedup": first_time / avg_time if avg_time > 0 else 0,
    }


def test_sync_endpoint(endpoint: str) -> dict[str, Any]:
    """Test a synchronous endpoint and return timing information"""
    url = f"{DEFAULT_URL}/{endpoint}"
    headers = {"X-API-KEY": API_KEY}

    # First call (expected cache miss)
    start_time = time.time()
    requests.get(url, headers=headers)
    first_time = time.time() - start_time

    # Subsequent calls (expected cache hits)
    times = []
    for _ in range(TEST_ITERATIONS - 1):
        start_time = time.time()
        requests.get(url, headers=headers)
        elapsed = time.time() - start_time
        times.append(elapsed)

    # Calculate average and other stats
    avg_time = statistics.mean(times) if times else 0

    return {
        "first_call": first_time,
        "avg_subsequent": avg_time,
        "all_times": [first_time] + times,
        "speedup": first_time / avg_time if avg_time > 0 else 0,
    }


async def run_comparison():
    """Run performance comparison tests"""
    print("🔍 ASYNC VS SYNC CACHE PERFORMANCE COMPARISON")
    print("=============================================")

    # Clear both sync and async caches at the start
    # We'd normally want to directly access the cache objects, but for this test
    # we'll assume they're cleared when the server starts

    print("\n🔄 Testing standard endpoint (/models)")
    sync_results = test_sync_endpoint("models")

    print(f"  First call: {sync_results['first_call']:.4f} seconds")
    print(f"  Average subsequent calls: {sync_results['avg_subsequent']:.4f} seconds")
    print(f"  Speedup: {sync_results['speedup']:.2f}x")

    # Test async endpoint
    async with aiohttp.ClientSession() as session:
        print("\n🔄 Testing async endpoint (/async/models)")
        async_results = await test_async_endpoint(session, "async/models")

        print(f"  First call: {async_results['first_call']:.4f} seconds")
        print(
            f"  Average subsequent calls: {async_results['avg_subsequent']:.4f} seconds"
        )
        print(f"  Speedup: {async_results['speedup']:.2f}x")

    # Compare the two approaches
    print("\n📊 COMPARISON")
    print("  First call:")
    sync_first = sync_results["first_call"]
    async_first = async_results["first_call"]
    first_diff_pct = ((sync_first - async_first) / sync_first) * 100
    print(f"  - Sync: {sync_first:.4f}s vs Async: {async_first:.4f}s")
    print(
        f"  - Async is {abs(first_diff_pct):.1f}% {'faster' if first_diff_pct > 0 else 'slower'}"
    )

    print("\n  Subsequent calls (cache hits):")
    sync_avg = sync_results["avg_subsequent"]
    async_avg = async_results["avg_subsequent"]
    avg_diff_pct = ((sync_avg - async_avg) / sync_avg) * 100
    print(f"  - Sync: {sync_avg:.4f}s vs Async: {async_avg:.4f}s")
    print(
        f"  - Async is {abs(avg_diff_pct):.1f}% {'faster' if avg_diff_pct > 0 else 'slower'}"
    )

    print("\n✅ Performance comparison complete!")


def main():
    """Main entry point"""
    asyncio.run(run_comparison())


if __name__ == "__main__":
    main()
