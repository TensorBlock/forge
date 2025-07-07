#!/usr/bin/env python3
"""
Utility script to clear all cache entries.
This is useful for testing and diagnosing cache-related issues.
"""

import os
import sys
from pathlib import Path

from app.core.cache import provider_service_cache, user_cache

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to the project root directory
os.chdir(script_dir)


def clear_caches():
    """Clear all cache entries and print statistics"""
    print("🔄 Clearing caches...")

    # Get cache stats before clearing
    user_stats_before = user_cache.stats()
    provider_stats_before = provider_service_cache.stats()

    # Clear caches
    user_cache.clear()
    provider_service_cache.clear()

    # Get cache stats after clearing
    user_stats_after = user_cache.stats()
    provider_stats_after = provider_service_cache.stats()

    # Print results
    print("\n✅ Cache clearing complete!")
    print("\n📊 User Cache Statistics:")
    print(
        f"  Before: {user_stats_before['entries']} entries, {user_stats_before['hits']} hits, {user_stats_before['misses']} misses"
    )
    print(f"  After: {user_stats_after['entries']} entries")

    print("\n📊 Provider Service Cache Statistics:")
    print(
        f"  Before: {provider_stats_before['entries']} entries, {provider_stats_before['hits']} hits, {provider_stats_before['misses']} misses"
    )
    print(f"  After: {provider_stats_after['entries']} entries")

    print("\n🔍 Cache hit rates:")
    print(f"  User Cache: {user_stats_before['hit_rate']:.2%}")
    print(f"  Provider Cache: {provider_stats_before['hit_rate']:.2%}")

    return True


def main():
    """Main entry point"""
    if clear_caches():
        print("\n✨ All caches have been cleared successfully.")
        sys.exit(0)
    else:
        print("\n❌ Failed to clear caches.")
        sys.exit(1)


if __name__ == "__main__":
    main()
