#!/usr/bin/env python3
"""Script to check how dotenv loads values from the .env file."""

import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def check_env_file(file_path):
    """Check if a file exists and print its contents."""
    path = Path(file_path)
    if path.exists():
        print(f"File exists: {path.absolute()}")
        print("File contents:")
        with open(path) as f:
            for line in f:
                if line.strip() and "=" in line:
                    key, value = line.strip().split("=", 1)
                    if key == "FORGE_API_KEY":
                        print(f"{key}={value[:8]}...")
                    else:
                        print(line.strip())
    else:
        print(f"File does not exist: {path.absolute()}")


def main():
    """Main function to check environment loading."""
    # Find the project root directory
    script_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    os.chdir(script_dir)  # Change to project root directory

    print("Python version:", sys.version)
    print("Current working directory:", os.getcwd())

    # Check local .env file
    print("\nChecking .env file in current directory:")
    check_env_file(".env")

    # Check find_dotenv
    print("\nUsing find_dotenv to locate .env file:")
    found_dotenv = find_dotenv()
    print(f"Found .env at: {found_dotenv}")
    if found_dotenv:
        check_env_file(found_dotenv)

    # Try loading with load_dotenv
    print("\nLoading environment variables with load_dotenv:")
    load_dotenv(verbose=True)

    # Check if variable was loaded
    api_key = os.getenv("FORGE_API_KEY", "")
    if api_key:
        print(f"FORGE_API_KEY loaded: {api_key[:8]}...")
    else:
        print("FORGE_API_KEY not loaded")

    # Check all environment variables (not just from .env)
    print("\nAll environment variables containing 'FORGE':")
    for key, value in os.environ.items():
        if "FORGE" in key:
            print(
                f"{key}={value[:8]}..." if key == "FORGE_API_KEY" else f"{key}={value}"
            )


if __name__ == "__main__":
    main()
