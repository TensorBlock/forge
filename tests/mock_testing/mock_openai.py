"""
Utilities for patching OpenAI's client with our mock client.
This allows tests to run without real API calls.
"""

import importlib.util
import os
import sys
from unittest.mock import patch

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the mock client
from app.services.providers.mock_provider import MockClient


# Create a mock openai module that can be used when the real one is not installed
class MockOpenAIModule:
    def __init__(self):
        self.OpenAI = MockClient
        self.AsyncOpenAI = MockClient


# Check if openai is installed
if importlib.util.find_spec("openai") is None:
    # Create a mock openai module
    mock_openai = MockOpenAIModule()
    # Add it to sys.modules so import statements work
    sys.modules["openai"] = mock_openai
    # Import the mock module
    import openai as _mock_openai  # noqa: F401


def enable_mock_openai():
    """
    Enable mocking of OpenAI's client for testing.
    This function returns a context manager that can be used with 'with'.

    Example:
        with enable_mock_openai():
            client = openai.OpenAI(api_key="fake-key")
            # All calls to client will use the mock implementation
    """
    # Create patchers
    openai_client_patcher = patch("openai.OpenAI", return_value=MockClient())

    # Start the patchers
    mock_openai_client = openai_client_patcher.start()

    try:
        yield mock_openai_client
    finally:
        # Stop the patchers
        openai_client_patcher.stop()


def patch_with_mock():
    """Decorator to patch OpenAI with mock client for a test function"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create patchers
            openai_client_patcher = patch("openai.OpenAI", return_value=MockClient())
            async_openai_client_patcher = patch(
                "openai.AsyncOpenAI", return_value=MockClient()
            )

            # Start the patchers
            openai_client_patcher.start()
            async_openai_client_patcher.start()

            try:
                # Run the function
                result = await func(*args, **kwargs)
                return result
            finally:
                # Stop the patchers
                openai_client_patcher.stop()
                async_openai_client_patcher.stop()

        return wrapper

    return decorator


class MockPatch:
    """
    Class-based helper for patching OpenAI in tests.
    This can be used as a context manager or standalone.
    """

    def __init__(self):
        self.openai_client_patcher = patch("openai.OpenAI", return_value=MockClient())
        self.async_openai_client_patcher = patch(
            "openai.AsyncOpenAI", return_value=MockClient()
        )
        self.patched = False

    def start(self):
        """Start patching OpenAI"""
        if not self.patched:
            self.openai_client_patcher.start()
            self.async_openai_client_patcher.start()
            self.patched = True
        return self

    def stop(self):
        """Stop patching OpenAI"""
        if self.patched:
            self.openai_client_patcher.stop()
            self.async_openai_client_patcher.stop()
            self.patched = False

    def __enter__(self):
        """Enter context manager"""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager"""
        self.stop()
