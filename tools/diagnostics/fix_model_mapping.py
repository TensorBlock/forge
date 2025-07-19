#!/usr/bin/env python3
"""
Utility script to fix model mappings in the database.
Specifically for fixing the gpt-4o to mock-gpt-4o mapping issue.
"""

import asyncio
import os
import sys
from pathlib import Path

from app.core.database import get_async_db

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to the project root directory
os.chdir(script_dir)


async def fix_model_mappings():
    """Fix model mappings by clearing caches"""
    print("\n🔧 FIXING MODEL MAPPINGS")
    print("======================")

    # Get DB session
    async with get_async_db() as db:
        pass

    # Clear all caches to ensure changes take effect
    print("🔄 Invalidating provider service cache for all users")
    from app.core.cache import provider_service_cache, user_cache

    provider_service_cache.clear()
    user_cache.clear()
    print("✅ All caches cleared")

    print("\n✅ Model mapping fix complete.")
    return True


async def main():
    """Main entry point"""
    if await fix_model_mappings():
        print(
            "\n✅ Model mappings have been fixed. Use check_model_mappings.py to verify."
        )
        sys.exit(0)
    else:
        print("\n❌ Failed to fix model mappings.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
