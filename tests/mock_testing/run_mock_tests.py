#!/usr/bin/env python3
"""
Run all mock tests from a single script.
"""

import asyncio
import os
import subprocess
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def print_header(text):
    """Print a header with decoration"""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)


async def run_mock_client_tests():
    """Run the mock client tests"""
    print_header("Running Mock Client Tests")

    # Get the path to the test_mock_client.py script
    script_path = os.path.join(os.path.dirname(__file__), "test_mock_client.py")

    # Run the script as a subprocess
    result = subprocess.run(
        ["python", script_path], capture_output=True, text=True, check=False
    )

    # Print the output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


async def run_example_tests():
    """Run the example tests"""
    print_header("Running Example Tests")

    # Get the path to the test_with_mocks.py script
    script_path = os.path.join(
        os.path.dirname(__file__), "examples", "test_with_mocks.py"
    )

    # Run the script as a subprocess with unittest discover
    result = subprocess.run(
        ["python", "-m", "unittest", script_path],
        capture_output=True,
        text=True,
        check=False,
    )

    # Print the output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


async def main():
    """Run all tests"""
    client_tests_ok = await run_mock_client_tests()
    example_tests_ok = await run_example_tests()

    print_header("Summary")
    print(f"Mock Client Tests: {'PASSED' if client_tests_ok else 'FAILED'}")
    print(f"Example Tests:     {'PASSED' if example_tests_ok else 'FAILED'}")

    if client_tests_ok and example_tests_ok:
        print("\n✅ All mock tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
