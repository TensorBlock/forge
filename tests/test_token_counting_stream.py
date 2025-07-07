#!/usr/bin/env python3
import argparse
import asyncio
import json
from http import HTTPStatus

import aiohttp


async def test_token_counting_stream(api_key: str, model: str):
    """
    Test the token counting in streaming mode.
    """
    url = "http://localhost:8000/v1/chat/completions"
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Write a short story about a robot learning to count. Keep it to 3 paragraphs.",
            },
        ],
        "stream": True,
    }

    print(f"\n[INFO] Sending streaming request to {url}")
    print(f"[INFO] Model: {model}")

    tokens_seen = 0
    chunk_count = 0

    # Use single with statement for session and post request
    async with (
        aiohttp.ClientSession() as session,
        session.post(url, headers=headers, json=payload) as response,
    ):
        print(f"[INFO] Response status: {response.status}")

        if response.status != HTTPStatus.OK:
            error_text = await response.text()
            print(f"[ERROR] {error_text}")
            return

        async for line_bytes in response.content:
            line = line_bytes.decode("utf-8").strip()

            if not line:
                continue

            if line.startswith("data:"):
                chunk_count += 1
                data_str = line[5:].strip()

                if data_str == "[DONE]":
                    print("\n[INFO] Streaming completed")
                    print(f"[INFO] Total chunks: {chunk_count}")
                    break

                try:
                    data = json.loads(data_str)

                    # Extract content from the chunk
                    content = ""
                    if (
                        "choices" in data
                        and data["choices"]
                        and "delta" in data["choices"][0]
                    ):
                        content = data["choices"][0]["delta"].get("content", "")

                    # Keep track of content length as a proxy for tokens
                    tokens_seen += len(content) / 4  # Simple approximation

                    # Check if we have usage information
                    if "usage" in data:
                        usage = data.get("usage", {})
                        print(f"\n[TOKEN INFO] Reported usage: {usage}")

                    if chunk_count % 10 == 1:
                        print(f"\n[CHUNK {chunk_count}] Content: '{content}'")
                        print(
                            f"[TOKEN ESTIMATE] Approximately {int(tokens_seen)} tokens so far"
                        )

                except json.JSONDecodeError:
                    print(f"[WARNING] Could not parse: {data_str}")

    print("\n[SUMMARY]")
    print(f"Total chunks received: {chunk_count}")
    print(f"Estimated token count: {int(tokens_seen)}")

    # After streaming completes, check the usage statistics
    print("\n[INFO] Checking usage statistics...")
    url = "http://localhost:8000/stats/"

    # Use single with statement for session and get request
    async with (
        aiohttp.ClientSession() as session,
        session.get(url, headers=headers) as response,
    ):
        if response.status == HTTPStatus.OK:
            usage_data = await response.json()
            print("\n[USAGE STATS]")
            print(json.dumps(usage_data, indent=2))
        else:
            print(f"[ERROR] Failed to get usage stats: {response.status}")
            error_text = await response.text()
            print(error_text)


def main():
    parser = argparse.ArgumentParser(
        description="Test token counting in streaming mode"
    )
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument(
        "--model", default="gpt-3.5-turbo", help="Model to use for the test"
    )

    args = parser.parse_args()

    asyncio.run(test_token_counting_stream(args.api_key, args.model))


if __name__ == "__main__":
    main()
