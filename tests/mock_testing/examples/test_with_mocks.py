#!/usr/bin/env python3
"""
Example tests that demonstrate using the mock client in different scenarios.
"""

import asyncio
import os
import sys
import unittest

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# Import our mock utilities
from tests.mock_testing.mock_openai import MockPatch, patch_with_mock


# This would be your application code that uses OpenAI
class MyAppService:
    """Example application service that uses OpenAI"""

    def __init__(self, api_key=None):
        """Initialize with an API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        # In a real app, you'd import OpenAI here
        # But we'll do it in the methods to allow for patching

    async def generate_response(self, user_message: str) -> str:
        """Generate a response to a user message"""
        import openai

        client = openai.OpenAI(api_key=self.api_key)

        response = await client.chat_completions_create(
            model="mock-only-gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
        )

        return response.choices[0].message.content

    async def get_available_models(self) -> list:
        """Get a list of available models"""
        import openai

        client = openai.OpenAI(api_key=self.api_key)

        models = await client.models_list()
        # Handle both object-style and dict-style responses
        if hasattr(models, "data") and hasattr(models.data[0], "id"):
            return [model.id for model in models.data]
        else:
            return [model["id"] for model in models.data]


# Now let's write tests for our application using the mock client
class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases"""

    def run_async(self, coro):
        """Run a coroutine in an event loop"""
        return asyncio.run(coro)


class TestMyAppWithMocks(AsyncTestCase):
    """Test the MyApp class with mocked OpenAI client"""

    def setUp(self):
        """Set up the test"""
        self.service = MyAppService(api_key="test-key")

    def test_generate_response(self):
        """Test generating a response with the mock client"""

        @patch_with_mock()
        async def _async_test():
            response = await self.service.generate_response("Hello, how are you?")

            # The mock response will be predictable
            self.assertIsNotNone(response)
            self.assertIn("You asked", response)  # Our mock adds this prefix
            return response

        self.run_async(_async_test())

    def test_get_models(self):
        """Test getting available models with the mock client"""

        @patch_with_mock()
        async def _async_test():
            models = await self.service.get_available_models()

            # The mock returns specific models
            self.assertIn("mock-gpt-3.5-turbo", models)
            self.assertIn("mock-gpt-4", models)
            return models

        self.run_async(_async_test())

    def test_with_context_manager(self):
        """Test using the mock client with a context manager"""

        async def _async_test():
            # Using the context manager approach
            mock_patch = MockPatch()
            with mock_patch:
                response = await self.service.generate_response("Tell me about testing")
                self.assertIsNotNone(response)
                self.assertIn("You asked", response)
            return response

        self.run_async(_async_test())


# If we run this directly, run all the tests
if __name__ == "__main__":
    unittest.main()
