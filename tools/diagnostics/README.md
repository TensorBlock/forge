# Forge Diagnostic Tools

This directory contains diagnostic tools for troubleshooting and analyzing the Forge application.

## Available Tools

- **check_db_keys.py**: Examines database for user API keys and compares with expected values
  - Usage: `python tools/diagnostics/check_db_keys.py`
  - Use this when investigating API key validation issues or unexpected authentication errors

- **check_dotenv.py**: Verifies environment variables loading from .env files
  - Usage: `python tools/diagnostics/check_dotenv.py`
  - Use this when diagnosing environment configuration issues

- **run_test_clean.py**: Runs frontend simulation tests in a clean environment
  - Usage: `python tools/diagnostics/run_test_clean.py`
  - Use this when system-level environment variables might be interfering with tests

- **clear_cache.py**: Clears all in-memory caches and shows statistics
  - Usage: `python tools/diagnostics/clear_cache.py`
  - Use this when testing cache behavior or diagnosing cache-related issues
  - Provides statistics about cache utilization before clearing

- **generate_cache_report.py**: Measures cache performance through repeated API calls
  - Usage: `python tools/diagnostics/generate_cache_report.py [--api-key KEY] [--clear]`
  - Use this to verify that caching is working properly and measure performance gains
  - Shows timing differences between uncached and cached API calls

- **enable_cache_debug.py**: This tool enables detailed cache debugging by modifying your `.env` file to set `DEBUG_CACHE=true`. When enabled, all cache operations (hits, misses, sets, deletes) will be logged to the console, making it easier to diagnose cache-related issues.

**Usage:**
```bash
python tools/diagnostics/enable_cache_debug.py
```

**When to use:**
- When troubleshooting performance issues that might be cache-related
- When you want to verify that caching is working as expected
- When diagnosing potential issues with stale cached data

- **compare_async_sync.py**: Compares the performance of synchronous vs. asynchronous cache implementations by testing both the regular `/models` endpoint and the `/async/models` endpoint.

**Usage:**
```bash
python tools/diagnostics/compare_async_sync.py
```

**When to use:**
- To measure performance improvements from async caching
- To verify that async caching is working correctly
- To understand the real-world impact of async vs. sync implementations
- When evaluating whether to migrate more endpoints to async patterns

- **check_model_mappings.py**: Displays all model mappings in the database and checks how models are routed to providers.

**Usage:**
```bash
python tools/diagnostics/check_model_mappings.py
```

**When to use:**
- When you're getting unexpected model behavior
- To verify which provider is handling specific models
- To debug model routing issues
- When you suspect a model is being routed to the wrong provider

- **fix_model_mapping.py**: Fixes issues with model mappings, particularly removing problematic mappings to mock providers.

**Usage:**
```bash
python tools/diagnostics/fix_model_mapping.py
```

**When to use:**
- When models are being incorrectly routed to mock providers
- To fix the specific issue where "gpt-4o" is mapped to "mock-gpt-4o"
- After checking model mappings with `check_model_mappings.py` and finding issues
- When you need to remap models to the correct providers

- **enable_request_logging.py**: Enables detailed request logging for the Forge server by setting the LOG_LEVEL to debug in the .env file.

**Usage:**
```bash
python tools/diagnostics/enable_request_logging.py
```

**When to use:**
- When you want to see all incoming requests and responses in the server logs
- When troubleshooting API requests that aren't producing expected results
- When you need visibility into request processing time
- To diagnose issues where the server appears to ignore requests

## Caching in Forge
Forge implements several caching mechanisms to improve performance:

1. **User Cache**: API keys are cached for 5 minutes to reduce database lookups during authentication
2. **Provider Service Cache**: Provider service instances are cached for 1 hour per user
3. **Model Cache**: Available models from providers are cached for 1 hour to reduce API calls
4. **Async Cache**: An async-compatible cache implementation for better performance in async contexts and future distributed cache support

Forge supports both synchronous and asynchronous caching patterns to maximize flexibility and performance:

- **Synchronous Cache**: Used in traditional request-response flows where backward compatibility is needed
- **Asynchronous Cache**: Used in async code paths for non-blocking operations and prepared for distributed caching

You can use the tools in this directory to monitor and test the cache performance.

## When to Use These Tools

Use these diagnostic tools when you need to troubleshoot various aspects of the Forge application:

- **Environment configuration issues**: Use check_dotenv.py to validate environment variables
- **API key and authentication problems**: Use check_db_keys.py to inspect database contents
- **Test failures**: Use run_test_clean.py to run tests in a clean environment
- **Cache-related issues**: Use clear_cache.py and generate_cache_report.py to verify and analyze caching behavior

These tools provide visibility into data that may be difficult to inspect during normal operation of the application.

> **Note:** Cache test scripts have been moved to the `tests/cache/` directory:
> - `tests/cache/test_sync_cache.py` - Tests synchronous caching
> - `tests/cache/test_async_cache.py` - Tests asynchronous caching
