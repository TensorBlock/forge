#!/usr/bin/env python3
import os
import sys
import unittest

# Add parent directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Patch bcrypt version detection to avoid warnings
import bcrypt

if not hasattr(bcrypt, "__about__"):
    import types

    bcrypt.__about__ = types.ModuleType("__about__")
    bcrypt.__about__.__version__ = (
        bcrypt.__version__ if hasattr(bcrypt, "__version__") else "3.2.0"
    )

# Import the cache test files
# These are run separately as they need special async setup
from tests.unit_tests.test_provider_service import TestProviderService

# Import the test modules
from tests.unit_tests.test_security import TestSecurity

# Import the image related tests
from tests.unit_tests.test_provider_service_images import TestProviderServiceImages


# Define test suites
def security_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestSecurity))
    return suite


def provider_service_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestProviderService))
    return suite

def provider_service_images_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestProviderServiceImages))
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)

    tests_to_run = []

    print("Running security tests...")
    result_security = runner.run(security_suite())
    tests_to_run.append(result_security)

    print("\nRunning provider service tests...")
    result_provider = runner.run(provider_service_suite())
    tests_to_run.append(result_provider)

    print("\nRunning provider service images tests...")
    result_provider_images = runner.run(provider_service_images_suite())
    tests_to_run.append(result_provider_images)

    # Integration tests require a running server
    print("\nFor integration tests, make sure the server is running and then execute:")
    print("python tests/integration_test.py")

    # Cache tests
    print("\nTo run cache tests:")
    print("python tests/cache/test_sync_cache.py  # For sync cache tests")
    print("python tests/cache/test_async_cache.py  # For async cache tests")

    # Frontend simulation tests require a valid Forge API key
    print(
        "\nTo simulate a frontend application, set your Forge API key in the .env file and run:"
    )
    print("python tests/frontend_simulation.py")

    # Mock provider tests
    print("\nTo run all mock tests at once:")
    print("python tests/mock_testing/run_mock_tests.py")

    print("\nOr to run individual mock tests:")
    print("python tests/mock_testing/test_mock_client.py")
    print("# For interactive testing:")
    print("python tests/mock_testing/test_mock_client.py --interactive")

    print("\nFor examples of using mocks in your tests, see:")
    print("python tests/mock_testing/examples/test_with_mocks.py")

    print("\nSee tests/mock_testing/README.md for more information on mock testing.")

    # Exit with error code if any tests failed
    if any(not test.wasSuccessful() for test in tests_to_run):
        sys.exit(1)