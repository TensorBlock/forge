#!/usr/bin/env python3
"""
Set up a test user with a known Forge API key and add a mock provider to it.
This script is used to prepare the environment for testing the mock provider.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from passlib.context import CryptContext

from app.core.cache import invalidate_user_cache, provider_service_cache
from app.core.database import SessionLocal
from app.core.security import encrypt_api_key
from app.models.provider_key import ProviderKey
from app.models.user import User

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Load environment variables from project root
os.chdir(script_dir)
load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Constants
TEST_USERNAME = "test_user"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword"  # This is just for testing
TEST_FORGE_API_KEY = "forge-test-mock-api-key"
MOCK_PROVIDER_API_KEY = "mock-api-key-for-testing-purposes"


def create_or_update_test_user():
    """Create a test user with a known Forge API key or update existing user"""
    db = SessionLocal()

    try:
        # Try to find user by username first
        user = db.query(User).filter(User.username == TEST_USERNAME).first()

        # If not found by username, try by email
        if not user:
            user = db.query(User).filter(User.email == TEST_EMAIL).first()

        # If user exists, update the forge API key
        if user:
            print(f"✅ Found existing user: {user.username} (email: {user.email})")
            old_key = user.forge_api_key
            user.forge_api_key = TEST_FORGE_API_KEY
            db.commit()
            db.refresh(user)
            # Invalidate the user in cache to force refresh with new API key
            invalidate_user_cache(old_key)
            invalidate_user_cache(TEST_FORGE_API_KEY)
            print(
                f"✅ Invalidated user cache for API keys: {old_key} and {TEST_FORGE_API_KEY}"
            )
            print(f"🔄 Updated Forge API Key: {old_key} -> {user.forge_api_key}")
            return user

        # Create new user if not exists
        hashed_password = pwd_context.hash(TEST_PASSWORD)
        user = User(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            hashed_password=hashed_password,
            forge_api_key=TEST_FORGE_API_KEY,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created test user '{TEST_USERNAME}'")
        print(f"🔑 Forge API Key: {TEST_FORGE_API_KEY}")
        return user

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating/updating test user: {str(e)}")
        return None
    finally:
        db.close()


def add_mock_provider_to_user(user_id):
    """Add a mock provider to the test user"""
    db = SessionLocal()

    try:
        # Check if the mock provider already exists for this user
        existing_provider = (
            db.query(ProviderKey)
            .filter(ProviderKey.user_id == user_id, ProviderKey.provider_name == "mock")
            .first()
        )

        if existing_provider:
            print("✅ Mock provider already exists for the test user.")
            return True

        # Create a mock API key
        encrypted_key = encrypt_api_key(MOCK_PROVIDER_API_KEY)

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
            user_id=user_id,
            provider_name="mock",
            encrypted_api_key=encrypted_key,
            model_mapping=json.dumps(model_mapping),
        )

        db.add(provider_key)
        db.commit()

        # Invalidate provider key cache for this user to force refresh
        provider_service_cache.delete(f"provider_keys:{user_id}")
        print(f"✅ Invalidated provider key cache for user ID: {user_id}")

        print("✅ Successfully added mock provider for test user.")
        print(f"🔑 Mock API Key: {MOCK_PROVIDER_API_KEY} (used for testing only)")
        print("")
        print("You can now use the following models with this provider:")
        for original, mock in model_mapping.items():
            print(f"  - {original} -> {mock}")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error setting up mock provider: {str(e)}")
        return False
    finally:
        db.close()


def main():
    """Set up a test user with a mock provider"""
    print("🔄 Setting up test user with mock provider...")

    # Create or update test user
    user = create_or_update_test_user()
    if not user:
        sys.exit(1)

    # Add mock provider to user
    if add_mock_provider_to_user(user.id):
        print("")
        print("✅ Setup complete!")
        print("📝 To test the mock provider, run:")
        print(
            f"python tests/mock_testing/test_mock_provider.py --api-key {TEST_FORGE_API_KEY}"
        )
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
