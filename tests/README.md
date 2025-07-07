# Forge Integration Tests

This directory contains tests for Forge, including unit tests and integration tests.

## Integration Tests

The main integration test script is:

- `integration_test.py` - Supports both local development with real API calls and mock mode for CI/CD environments

### Prerequisites

Before running integration tests, make sure:

1. The Forge server is running (`python run.py` from the project root)
2. Required Python packages are installed:
   ```
   pip install requests python-dotenv
   ```

### Running Integration Tests

You can run the integration tests in different modes:

#### With Real API Calls

For local development with actual API calls to external providers:

```bash
# Run the full integration test (requires API keys)
python tests/integration_test.py
```

This test will register a user, add provider keys, and test completions with real API calls. You'll need:

- OpenAI API key (set as OPENAI_API_KEY in .env)
- (Optional) Anthropic API key (set as ANTHROPIC_API_KEY in .env)

#### With Mocked Responses

For CI environments or when you don't want to make real API calls:

```bash
# Use CI testing mode
CI_TESTING=true python tests/integration_test.py

# Or use the SKIP_API_CALLS flag (same effect)
SKIP_API_CALLS=true python tests/integration_test.py
```

In mock mode:
- External API calls are replaced with mock responses
- The server connection is still verified
- User registration and management features are tested
- API interactions use the mock provider to simulate responses
- The mock provider returns predefined responses for testing

### Mock Provider

The integration test uses the mock provider from `app/services/providers/mock_provider.py` when running in mock mode. This provider:

- Simulates API responses without making actual API calls
- Provides mock models similar to those from real providers
- Returns consistent, predictable responses for testing
- Can be used with the `CI_TESTING=true` or `SKIP_API_CALLS=true` flag

### GitHub Actions Integration

The test is automatically run in GitHub Actions workflows defined in `.github/workflows/tests.yml`. The workflow:

1. Sets up a test environment
2. Starts the Forge server
3. Runs the integration tests in CI mode
4. Ensures no actual API calls are made to external services

## Unit Tests

Run individual unit tests with:

```bash
python -m unittest tests/test_security.py
python -m unittest tests/test_provider_service.py
```

Run all unit tests with:

```bash
python -m unittest discover tests
```

## Cache Tests

The cache test directory contains tests for both synchronous and asynchronous caching functionality:

- `test_sync_cache.py` - Tests the synchronous in-memory caching with ProviderService instances
- `test_async_cache.py` - Tests the async-compatible cache implementation for future distributed caching

### Running Cache Tests

```bash
# Run synchronous cache tests
python tests/cache/test_sync_cache.py

# Run asynchronous cache tests
python tests/cache/test_async_cache.py
```

These tests verify:
- Cache hit/miss behavior
- Performance improvements from caching
- Proper instance reuse with singleton pattern
- AsyncCache compatibility with asyncio patterns

The async tests are important for validating Forge's readiness for distributed caching solutions like Redis or AWS ElasticCache, as outlined in `docs/DISTRIBUTED_CACHE_MIGRATION.md`.

## Test Coverage Report

Generate a test coverage report with:

```bash
pytest tests/test_*.py --cov=app --cov-report=xml
```
