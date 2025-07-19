#!/usr/bin/env python3
"""
Utility script to add a mock provider to a user account for testing purposes.
This allows users to test the Forge middleware without needing real API keys.
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.core.cache import provider_service_cache
from app.core.database import AsyncSessionLocal
from app.core.security import encrypt_api_key
from app.models.provider_key import ProviderKey
from app.models.user import User
from sqlalchemy import select

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Load environment variables
load_dotenv()

# Change to the project root directory to ensure proper environment loading
os.chdir(script_dir)


async def setup_mock_provider(username: str, force: bool = False):
    """Add a mock provider key to the specified user account"""
    # Create a database session
    async with AsyncSessionLocal() as db:
        try:
            # Find the user
            result = await db.execute(select(User).filter(User.username == username))
            user = result.scalar_one_or_none()
            if not user:
                print(f"❌ User '{username}' not found. Please provide a valid username.")
                return False

            # Check if the mock provider already exists for this user
            result = await db.execute(select(ProviderKey).filter(ProviderKey.user_id == user.id, ProviderKey.provider_name == "mock"))
            existing_provider = result.scalar_one_or_none()

            if existing_provider and not force:
                print(f"⚠️ Mock provider already exists for user '{username}'.")
                print("Use --force to replace it.")
                return False

            # If force is set and provider exists, delete the existing one
            if existing_provider and force:
                db.delete(existing_provider)
                db.commit()
                print(f"🗑️ Deleted existing mock provider for user '{username}'.")

            # Create a mock API key - it doesn't need to be secure as it's not used
            mock_api_key = "mock-api-key-for-testing-purposes"
            encrypted_key = encrypt_api_key(mock_api_key)

            # Create model mappings for common models to their mock equivalents
            model_mapping = {
                "mock-only-gpt-3.5-turbo": "mock-gpt-3.5-turbo",
                "mock-only-gpt-4": "mock-gpt-4",
                "mock-only-gpt-4o": "mock-gpt-4o",
                "mock-only-claude-3-opus": "mock-claude-3-opus",
                "mock-only-claude-3-sonnet": "mock-claude-3-sonnet",
                "mock-only-claude-3-haiku": "mock-claude-3-haiku",
            }

            # Create the provider key
            provider_key = ProviderKey(
                user_id=user.id,
                provider_name="mock",
                encrypted_api_key=encrypted_key,
                model_mapping=json.dumps(
                    model_mapping
                ),  # Use json.dumps for proper storage
            )

            db.add(provider_key)
            db.commit()

            # Invalidate provider key cache for this user to force refresh
            provider_service_cache.delete(f"provider_keys:{user.id}")
            print(f"✅ Invalidated provider key cache for user '{username}'")

            print(f"✅ Successfully added mock provider for user '{username}'.")
            print(
                f"🔑 Mock API Key: {mock_api_key} (not a real key, used for testing only)"
            )
            print("")
            print("You can now use the following models with this provider:")
            for original, mock in model_mapping.items():
                print(f"  - {original} -> {mock}")
            print("")
            print(
                "Use these models with your Forge API Key to test the middleware without real API calls."
            )

            return True

        except Exception as e:
            await db.rollback()
            print(f"❌ Error setting up mock provider: {str(e)}")
            return False


async def main():
    parser = argparse.ArgumentParser(
        description="Add a mock provider to a user account for testing"
    )
    parser.add_argument(
        "username", help="Username of the account to add the mock provider to"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Replace existing mock provider if it exists",
    )

    args = parser.parse_args()

    if setup_mock_provider(args.username, args.force):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
