#!/usr/bin/env python3
"""
Script to run the test with a clean environment.
"""

import os
import subprocess
import sys


def main():
    """Run the test in a clean environment."""
    # Find the project root directory (where this script is located)
    script_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    os.chdir(script_dir)  # Change to project root directory

    # Create a clean environment without the problematic variable
    clean_env = os.environ.copy()
    if "FORGE_API_KEY" in clean_env:
        del clean_env["FORGE_API_KEY"]

    # Run the test with the clean environment
    result = subprocess.run(
        [sys.executable, "tests/frontend_simulation.py"], env=clean_env, check=False
    )

    print(f"\nTest completed with exit code: {result.returncode}")


if __name__ == "__main__":
    main()
