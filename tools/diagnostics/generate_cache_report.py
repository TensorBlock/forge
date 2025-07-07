#!/usr/bin/env python3
"""
Generate a cache performance report by making repeated API calls and measuring hit rates.
"""

import argparse
import os
import sys
import time
from http import HTTPStatus
from pathlib import Path

import requests

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to project root
os.chdir(script_dir)

# Constants
DEFAULT_FORGE_API_KEY = "forge-test-mock-api-key"
DEFAULT_URL = "http://localhost:8000"
TEST_ITERATIONS = 3  # Number of times to repeat each API call


def make_api_call(endpoint, headers, data=None, method="GET"):
    """Make an API call and return the response"""
    url = f"{DEFAULT_URL}/{endpoint}"

    if method == "GET":
        response = requests.get(url, headers=headers)
    else:  # POST
        response = requests.post(url, headers=headers, json=data)

    return response


def run_cache_test(
    api_key=DEFAULT_FORGE_API_KEY, endpoint="models", method="GET", data=None
):
    """Run a cache test by repeatedly calling an API endpoint"""

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    print(f"\n🔄 Testing cache for endpoint: /{endpoint}")
    print(f"Running {TEST_ITERATIONS} iterations...")

    # First call (expected cache miss)
    start_time = time.time()
    response = make_api_call(endpoint, headers, data, method)
    first_time = time.time() - start_time

    if response.status_code != HTTPStatus.OK:
        print(f"❌ First API call failed: {response.status_code} - {response.text}")
        return

    print(f"✅ First call (cache miss): {first_time:.3f} seconds")

    # Subsequent calls (expected cache hits)
    times = []
    for i in range(TEST_ITERATIONS - 1):
        start_time = time.time()
        response = make_api_call(endpoint, headers, data, method)
        elapsed = time.time() - start_time
        times.append(elapsed)

        if response.status_code != HTTPStatus.OK:
            print(
                f"❌ API call #{i + 2} failed: {response.status_code} - {response.text}"
            )
            continue

        print(f"✅ Call #{i + 2}: {elapsed:.3f} seconds")

    # Calculate and print statistics
    if times:
        avg_time = sum(times) / len(times)
        speedup = first_time / avg_time if avg_time > 0 else 0

        print("\n📊 Cache Performance:")
        print(f"  First call (likely miss): {first_time:.3f} seconds")
        print(f"  Average cached calls: {avg_time:.3f} seconds")
        print(f"  Cache speedup: {speedup:.1f}x")

    return response


def main():
    parser = argparse.ArgumentParser(description="Generate a cache performance report")
    parser.add_argument(
        "--api-key",
        "-k",
        default=DEFAULT_FORGE_API_KEY,
        help=f"Forge API key (default: {DEFAULT_FORGE_API_KEY})",
    )
    parser.add_argument(
        "--clear",
        "-c",
        action="store_true",
        help="Clear the cache before running tests",
    )

    args = parser.parse_args()

    # Clear cache if requested
    if args.clear:
        try:
            # Import directly from our app
            from app.core.cache import provider_service_cache, user_cache

            print("🔄 Clearing caches...")
            user_cache.clear()
            provider_service_cache.clear()
            print("✅ Caches cleared")
        except ImportError:
            print("⚠️ Unable to directly clear caches. Run clear_cache.py separately.")

    print("\n🔍 CACHE PERFORMANCE REPORT")
    print("=========================")

    # Test the models endpoint (GET)
    run_cache_test(api_key=args.api_key, endpoint="models", method="GET")

    # Test chat completions endpoint (POST)
    chat_data = {
        "model": "mock-gpt-4",
        "messages": [{"role": "user", "content": "Hello, testing cache performance"}],
    }
    run_cache_test(
        api_key=args.api_key, endpoint="chat/completions", method="POST", data=chat_data
    )

    # Test text completions endpoint (POST)
    completion_data = {
        "model": "mock-gpt-3.5-turbo",
        "prompt": "Test cache performance for text completion",
    }
    run_cache_test(
        api_key=args.api_key,
        endpoint="completions",
        method="POST",
        data=completion_data,
    )

    print("\n✨ Cache performance testing complete!")
    print(
        "In the results above, significant speedup in subsequent calls indicates effective caching."
    )


if __name__ == "__main__":
    main()
