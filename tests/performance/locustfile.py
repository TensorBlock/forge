"""
Locust load testing file for Forge API.

This file defines load testing scenarios for the Forge API using Locust.
It measures performance under various load conditions and user behaviors.

Usage:
    1. Start the Forge server
    2. Run: locust -f tests/performance/locustfile.py
    3. Open http://localhost:8089 in your browser
"""

import json
import os
import random
import time
from pathlib import Path

import locust.stats
from dotenv import load_dotenv
from locust import HttpUser, between, events, task

# Load environment variables
load_dotenv()

# Configure Locust
locust.stats.CSV_STATS_INTERVAL_SEC = 5  # Default is 1 second
locust.stats.CSV_STATS_FLUSH_INTERVAL_SEC = 60  # Default is 10 seconds

# Get Forge API key from .env file or environment variables
FORGE_API_KEY = os.getenv("FORGE_API_KEY")

# Fallback to predefined API key for tests
if not FORGE_API_KEY:
    FORGE_API_KEY = "forge-test-mock-api-key"
    print("⚠️ No FORGE_API_KEY found in .env file. Using test key.")
else:
    print(f"✅ Using FORGE_API_KEY from environment: {FORGE_API_KEY[:8]}...")

# Constants
HTTP_STATUS_OK = 200  # HTTP status code for successful requests

# Sample prompts of different sizes for testing
SMALL_PROMPTS = [
    "What is machine learning?",
    "Explain quantum computing in simple terms.",
    "What are the benefits of clean energy?",
    "How does blockchain work?",
    "What is the significance of the number 42?",
]

MEDIUM_PROMPTS = [
    "Write a short summary about the impact of artificial intelligence on healthcare in the last decade.",
    "Compare and contrast renewable energy sources like solar, wind, and hydroelectric power.",
    "Explain how climate change affects biodiversity and what can be done to mitigate these effects.",
    "Discuss the ethical implications of autonomous vehicles in urban environments.",
    "Analyze the pros and cons of remote work for both employers and employees.",
]

LARGE_PROMPTS = [
    "Write a comprehensive analysis of how quantum computing could impact cryptography and data security. Include potential vulnerabilities and new security paradigms that might emerge.",
    "Provide a detailed explanation of how large language models work, their architecture, training process, and the ethical considerations in their development and deployment.",
    "Compare the healthcare systems of at least three different countries, analyzing their strengths, weaknesses, coverage models, and outcomes. Suggest potential improvements.",
    "Analyze the global supply chain disruptions caused by recent global events and suggest strategies for businesses to build resilience against future disruptions.",
    "Discuss the potential impact of clean energy transition on global economics, including job markets, international relations, and developing economies.",
]

# Models to test
DEFAULT_MODELS = ["mock-only-gpt-3.5-turbo", "mock-only-gpt-4"]


class ForgeApiUser(HttpUser):
    """
    Simulates a user of the Forge API making various types of requests.
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Setup the user session"""
        self.client.headers = {
            "X-API-KEY": FORGE_API_KEY,
            "Content-Type": "application/json",
        }

        # Get available models
        try:
            response = self.client.get("/models")
            if response.status_code == HTTP_STATUS_OK:
                data = response.json()
                self.models = [model["id"] for model in data.get("data", [])]
                if not self.models:
                    self.models = DEFAULT_MODELS
            else:
                self.models = DEFAULT_MODELS
        except Exception:
            self.models = DEFAULT_MODELS

    @task(10)  # Higher weight - will be executed more frequently
    def chat_completion_small(self):
        """Make a chat completion request with a small prompt"""
        model = random.choice(self.models)
        prompt = random.choice(SMALL_PROMPTS)

        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        with self.client.post(
            "/chat/completions", json=payload, name="Chat Completion - Small Prompt"
        ) as response:
            if response.status_code == HTTP_STATUS_OK:
                response.json()
                # You can track additional metrics here if needed

    @task(5)  # Medium weight
    def chat_completion_medium(self):
        """Make a chat completion request with a medium prompt"""
        model = random.choice(self.models)
        prompt = random.choice(MEDIUM_PROMPTS)

        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        with self.client.post(
            "/chat/completions", json=payload, name="Chat Completion - Medium Prompt"
        ) as _:
            pass  # Process response if needed

    @task(2)  # Lower weight - executed less frequently
    def chat_completion_large(self):
        """Make a chat completion request with a large prompt"""
        model = random.choice(self.models)
        prompt = random.choice(LARGE_PROMPTS)

        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}

        with self.client.post(
            "/chat/completions", json=payload, name="Chat Completion - Large Prompt"
        ) as _:
            pass  # Process response if needed

    @task(3)
    def chat_completion_streaming(self):
        """Make a streaming chat completion request"""
        model = random.choice(self.models)
        prompt = random.choice(MEDIUM_PROMPTS)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        # Note: Locust doesn't handle streaming responses well for metrics
        # This is mostly to test if streaming works and measure basic timing
        time.time()
        with self.client.post(
            "/chat/completions",
            json=payload,
            name="Chat Completion - Streaming",
            stream=True,
        ) as response:
            if response.status_code == HTTP_STATUS_OK:
                # Read the streaming response
                for _ in response.iter_lines():
                    pass  # Just consume the stream

    @task(15)  # Highest frequency - simulates frequent model listing
    def list_models(self):
        """List available models"""
        self.client.get("/models", name="List Models")


# Locust events


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Event handler called when the load test starts.
    """
    print(f"Test is starting with {environment.runner.user_count} initial users")

    # Create results directory if it doesn't exist
    results_dir = Path(__file__).parent / "results" / "locust"
    results_dir.mkdir(exist_ok=True, parents=True)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Event handler called when the load test stops.
    """
    print(
        f"Test stopped after running for {environment.runner.stats.total.avg_response_time:.2f}ms average response time"
    )

    # Save stats to file
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    stats_file = (
        Path(__file__).parent / "results" / "locust" / f"stats_{timestamp}.json"
    )

    stats = {
        "total_requests": environment.runner.stats.total.num_requests,
        "total_failures": environment.runner.stats.total.num_failures,
        "avg_response_time": environment.runner.stats.total.avg_response_time,
        "median_response_time": environment.runner.stats.total.median_response_time,
        "min_response_time": environment.runner.stats.total.min_response_time,
        "max_response_time": environment.runner.stats.total.max_response_time,
        "requests_per_second": environment.runner.stats.total.current_rps,
        "timestamp": timestamp,
        "endpoint_stats": {},
    }

    # Add stats for each endpoint
    for name, stats_entry in environment.runner.stats.entries.items():
        stats["endpoint_stats"][name] = {
            "requests": stats_entry.num_requests,
            "failures": stats_entry.num_failures,
            "avg_response_time": stats_entry.avg_response_time,
            "median_response_time": stats_entry.median_response_time,
            "90th_percentile": stats_entry.get_response_time_percentile(0.9),
            "95th_percentile": stats_entry.get_response_time_percentile(0.95),
            "99th_percentile": stats_entry.get_response_time_percentile(0.99),
        }

    # Save to file
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Test statistics saved to: {stats_file}")
