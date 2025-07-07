#!/usr/bin/env python3
"""
Enable request logging by setting LOG_LEVEL environment variable.
This script modifies the .env file to adjust the logging level for the Forge server.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir))

# Change to the project root directory
os.chdir(script_dir)


def enable_request_logging():
    """Enable request logging by setting LOG_LEVEL=debug in .env file"""
    env_file = Path(".env")

    # Read existing .env file
    if env_file.exists():
        with open(env_file) as f:
            lines = f.readlines()
    else:
        lines = []

    # Check if LOG_LEVEL already exists
    log_level_exists = False
    for i, line in enumerate(lines):
        if line.strip().startswith("LOG_LEVEL="):
            lines[i] = "LOG_LEVEL=debug\n"
            log_level_exists = True
            break

    # Add LOG_LEVEL if it doesn't exist
    if not log_level_exists:
        lines.append("\n# Set logging level for server\nLOG_LEVEL=debug\n")

    # Write back to .env file
    with open(env_file, "w") as f:
        f.writelines(lines)

    print("✅ Request logging enabled in .env file")
    print("🔍 Log level set to 'debug' to show detailed request/response information")
    print("ℹ️ Restart your server for changes to take effect")
    print("\nTo see all requests in the server logs, restart with:")
    print("    python run.py")

    return True


def main():
    """Main entry point"""
    if enable_request_logging():
        print("\n✨ Your server will now show detailed request logs")
        sys.exit(0)
    else:
        print("\n❌ Failed to enable request logging")
        sys.exit(1)


if __name__ == "__main__":
    main()
