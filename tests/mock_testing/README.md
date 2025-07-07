# Mock Testing in Forge

This directory contains tools for testing Forge with mock providers that simulate API responses without making actual API calls.

## Key Components

- `app/services/providers/mock_provider.py`: A module that provides mock implementations of API clients and response objects
- `tests/mock_testing/mock_openai.py`: Utilities for patching the OpenAI client with our mock implementation
- `tests/mock_testing/test_mock_client.py`: A demonstration of using the mock client directly
- `tests/mock_testing/examples/test_with_mocks.py`: Example tests showing different ways to use the mocks
- `tests/mock_testing/add_mock_provider.py`: Utility to add a mock provider to a user account for testing
- `tests/mock_testing/test_mock_provider.py`: Test script to verify the mock provider works with Forge API

## Using the Mock Client

The mock client can be used in several ways:

### 1. Direct Usage

You can use the `MockClient` directly as a drop-in replacement for OpenAI's client:

```python
from app.services.providers.mock_provider import MockClient

# Create a mock client
client = MockClient()

# Use it like you would use OpenAI's client
response = await client.chat_completions_create(
    model="mock-only-gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### 2. Patching OpenAI in Tests

For unit tests, you can patch the OpenAI client with our mock:

```python
from tests.mock_testing.mock_openai import MockPatch, patch_with_mock

# Using the decorator
@patch_with_mock()
async def test_something():
    import openai
    client = openai.OpenAI()
    # This will use our mock client

# Using the context manager
async def test_something_else():
    with MockPatch():
        import openai
        client = openai.OpenAI()
        # This will use our mock client
```

### 3. Using without OpenAI Package Installed

A special feature of our mock testing system is that it can work even when the OpenAI package is not installed:

```python
# Import our mock module first
from tests.mock_testing.mock_openai import openai

# Now you can use it as if you had the real OpenAI package
client = openai.OpenAI()
response = await client.chat_completions_create(
    model="mock-only-gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

This is particularly useful for CI/CD environments where you don't want to install the actual OpenAI package.

## Interactive Testing

You can run an interactive test using the mock client:

```bash
python tests/mock_testing/test_mock_client.py --interactive
```

This allows you to chat with the mock client to test how your application would behave without making real API calls.

## Automated Tests

To run all the automated tests:

```bash
python tests/mock_testing/test_mock_client.py
```

## Mock Models

The mock client supports these models:

- `mock-only-gpt-3.5-turbo` (maps to `mock-gpt-3.5-turbo`)
- `mock-only-gpt-4` (maps to `mock-gpt-4`)
- `mock-only-gpt-4o` (maps to `mock-gpt-4o`)
- `mock-only-claude-3-opus` (maps to `mock-claude-3-opus`)
- `mock-only-claude-3-sonnet` (maps to `mock-claude-3-sonnet`)
- `mock-only-claude-3-haiku` (maps to `mock-claude-3-haiku`)

## Benefits of Mock Testing

- No API keys required
- No usage costs
- Faster test execution
- Predictable responses for deterministic tests
- No network dependencies
- Can be used in CI/CD pipelines
- Can run even without the OpenAI package installed

## Mock Provider Setup and Testing

### Adding a Mock Provider

You can add a mock provider to a user account for testing purposes using:

```bash
# From project root
python tests/mock_testing/add_mock_provider.py <username>

# To replace an existing mock provider for the user
python tests/mock_testing/add_mock_provider.py <username> --force
```

This adds a mock provider to the specified user's account with a predefined API key. The user can then make requests to the Forge API with models prefixed with "mock-" to test functionality without making real API calls.

### Testing the Mock Provider

To verify that the mock provider is working correctly with Forge:

```bash
# From project root
python tests/mock_testing/test_mock_provider.py

# With a specific API key
python tests/mock_testing/test_mock_provider.py --api-key YOUR_FORGE_API_KEY

# With a custom API endpoint
python tests/mock_testing/test_mock_provider.py --url http://your-forge-instance:8000
```

This runs a series of tests against the Forge API using the mock provider, including chat completions, text completions, streaming, and model listing.
