import os
import sys
from unittest import IsolatedAsyncioTestCase as TestCase

# Add the parent directory to the path so Python can find the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch bcrypt version detection to avoid warnings
import bcrypt

if not hasattr(bcrypt, "__about__"):
    import types

    bcrypt.__about__ = types.ModuleType("__about__")
    bcrypt.__about__.__version__ = (
        bcrypt.__version__ if hasattr(bcrypt, "__version__") else "3.2.0"
    )

from jose import jwt

from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    decrypt_api_key,
    encrypt_api_key,
    generate_forge_api_key,
    get_password_hash,
    verify_password,
)


class TestSecurity(TestCase):
    """Test the security utilities"""

    async def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password123"
        hashed = get_password_hash(password)

        # Verify the hash is different from the original password
        self.assertNotEqual(password, hashed)

        # Verify the password against the hash
        self.assertTrue(verify_password(password, hashed))

        # Verify wrong password fails
        self.assertFalse(verify_password("wrong_password", hashed))

    async def test_jwt_token(self):
        """Test JWT token creation and verification"""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        # Decode and verify the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check that original data is preserved
        self.assertEqual(payload["sub"], "testuser")

        # Check that expiration is added
        self.assertIn("exp", payload)

    async def test_api_key_encryption(self):
        """Test API key encryption and decryption"""
        original_key = "sk-123456789abcdef"

        # Encrypt the key
        encrypted = encrypt_api_key(original_key)

        # Verify encrypted key is different
        self.assertNotEqual(original_key, encrypted)

        # Decrypt and verify
        decrypted = decrypt_api_key(encrypted)
        self.assertEqual(original_key, decrypted)

    async def test_forge_api_key_generation(self):
        """Test Forge API key generation"""
        key1 = generate_forge_api_key()
        key2 = generate_forge_api_key()

        # Check the format
        self.assertTrue(key1.startswith("forge-"))

        # Check uniqueness
        self.assertNotEqual(key1, key2)

        # Check length
        self.assertEqual(
            len(key1), 42
        )  # "forge-" (6) + checksum (4) + base_key (32 hex chars)
