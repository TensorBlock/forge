#!/usr/bin/env python3
"""
Analysis script for performance test results.

This script loads test results from the results directory and generates
visualizations and comparison reports.

Usage:
    python tests/performance/analyze_results.py
    python tests/performance/analyze_results.py --baseline baseline_file.json --new new_file.json
"""

import argparse
import base64
import json
from datetime import datetime
from glob import glob
from pathlib import Path

import matplotlib.pyplot as plt

# Setup directories
SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"
JSON_RESULTS_DIR = RESULTS_DIR / "json"
GRAPH_DIR = RESULTS_DIR / "graphs"

# Constants
MIN_RESULTS_FOR_COMPARISON = 2  # Minimum number of results needed for comparison
MIN_SEGMENTS_FOR_DEGRADATION = (
    2  # Minimum number of segments needed for degradation calculation
)
HTTP_STATUS_OK = 200  # HTTP status code for successful requests


def list_result_files() -> list[str]:
    """List all result JSON files"""
    return glob(str(JSON_RESULTS_DIR / "*.json"))


def load_result(filename: str) -> dict:
    """Load a result file"""
    with open(filename) as f:
        return json.load(f)


def compare_results(baseline: dict, new: dict) -> dict:
    """
    Compare two result sets.

    Args:
        baseline: Baseline results
        new: New results to compare

    Returns:
        Dictionary with comparison metrics
    """
    comparison = {
        "test_name": new.get("test_name", "Unknown"),
        "baseline_timestamp": baseline.get("timestamp", "Unknown"),
        "new_timestamp": new.get("timestamp", "Unknown"),
        "metrics": {},
    }

    # Compare metrics
    baseline_metrics = baseline.get("metrics", {})
    new_metrics = new.get("metrics", {})

    if "stats" in baseline_metrics and "stats" in new_metrics:
        # Compare latency stats
        baseline_stats = baseline_metrics["stats"]
        new_stats = new_metrics["stats"]

        comparison["metrics"]["latency"] = {
            "mean": {
                "baseline": baseline_stats.get("mean", 0),
                "new": new_stats.get("mean", 0),
                "change_pct": (
                    (new_stats.get("mean", 0) / baseline_stats.get("mean", 1)) - 1
                )
                * 100,
            },
            "median": {
                "baseline": baseline_stats.get("median", 0),
                "new": new_stats.get("median", 0),
                "change_pct": (
                    (new_stats.get("median", 0) / baseline_stats.get("median", 1)) - 1
                )
                * 100,
            },
            "p90": {
                "baseline": baseline_stats.get("p90", 0),
                "new": new_stats.get("p90", 0),
                "change_pct": (
                    (new_stats.get("p90", 0) / baseline_stats.get("p90", 1)) - 1
                )
                * 100,
            },
            "p99": {
                "baseline": baseline_stats.get("p99", 0),
                "new": new_stats.get("p99", 0),
                "change_pct": (
                    (new_stats.get("p99", 0) / baseline_stats.get("p99", 1)) - 1
                )
                * 100,
            },
        }

    if "success_rate" in baseline_metrics and "success_rate" in new_metrics:
        # Compare success rate
        comparison["metrics"]["success_rate"] = {
            "baseline": baseline_metrics["success_rate"],
            "new": new_metrics["success_rate"],
            "change_pct": new_metrics["success_rate"]
            - baseline_metrics["success_rate"],
        }

    # Compare throughput if available
    if "throughput" in baseline_metrics and "throughput" in new_metrics:
        baseline_throughput = baseline_metrics["throughput"]
        new_throughput = new_metrics["throughput"]

        # Handle different formats of throughput data
        if isinstance(baseline_throughput, dict) and isinstance(new_throughput, dict):
            # Dictionary format (may contain avg_req_per_sec)
            if (
                "avg_req_per_sec" in baseline_throughput
                and "avg_req_per_sec" in new_throughput
            ):
                baseline_value = baseline_throughput["avg_req_per_sec"]
                new_value = new_throughput["avg_req_per_sec"]
                comparison["metrics"]["throughput"] = {
                    "baseline": baseline_value,
                    "new": new_value,
                    "change_pct": ((new_value / baseline_value) - 1) * 100
                    if baseline_value > 0
                    else 0,
                }
        elif isinstance(baseline_throughput, int | float) and isinstance(
            new_throughput, int | float
        ):
            # Direct numeric values
            comparison["metrics"]["throughput"] = {
                "baseline": baseline_throughput,
                "new": new_throughput,
                "change_pct": ((new_throughput / baseline_throughput) - 1) * 100
                if baseline_throughput > 0
                else 0,
            }

    return comparison


def create_latency_bar_chart(
    results: dict, title: str, output_file: str | None = None
) -> None:
    """
    Create a bar chart comparing latency metrics.

    Args:
        results: Results data
        title: Chart title
        output_file: Output file path
    """
    metrics = results.get("metrics", {})
    stats = metrics.get("stats", {})

    if not stats:
        print(f"No stats found in results for {title}")
        return

    # Extract latency metrics
    metrics_to_plot = ["min", "mean", "median", "p90", "p99"]
    values = [stats.get(metric, 0) for metric in metrics_to_plot]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(metrics_to_plot, values, color="skyblue")
    plt.title(title)
    plt.ylabel("Latency (seconds)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height + 0.02,
            f"{height:.4f}s",
            ha="center",
            va="bottom",
        )

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved chart to {output_file}")
    else:
        plt.show()

    plt.close()


def create_throughput_comparison_chart(
    results: list[dict], title: str, output_file: str | None = None
) -> None:
    """
    Create a chart comparing throughput across concurrency levels.

    Args:
        results: List of result data dictionaries
        title: Chart title
        output_file: Output file path
    """
    concurrency_levels = []
    throughputs = []

    for result in results:
        # Check both in the metrics directly and in the data.metrics structure
        metrics = result.get("metrics", {})
        if not metrics:
            metrics = result.get("data", {}).get("metrics", {})

        if "concurrency" in metrics and "throughput" in metrics:
            concurrency = metrics["concurrency"]
            throughput_data = metrics["throughput"]
            throughput = 0
            if (
                isinstance(throughput_data, dict)
                and "avg_req_per_sec" in throughput_data
            ):
                throughput = throughput_data["avg_req_per_sec"]
            concurrency_levels.append(concurrency)
            throughputs.append(throughput)
        else:
            print(
                f"No stats found in results for {title} - {result.get('timestamp', 'unknown')}"
            )

    if not concurrency_levels:
        print(f"No throughput data found for {title}")
        return

    # Sort by concurrency
    sorted_data = sorted(zip(concurrency_levels, throughputs, strict=False))
    concurrency_levels, throughputs = zip(*sorted_data, strict=False)

    plt.figure(figsize=(10, 6))
    plt.plot(concurrency_levels, throughputs, marker="o", linestyle="-", color="green")
    plt.title(title)
    plt.xlabel("Concurrency Level")
    plt.ylabel("Requests per Second")
    plt.grid(True, linestyle="--", alpha=0.7)

    # Add value labels
    for x, y in zip(concurrency_levels, throughputs, strict=False):
        plt.text(x, y + 0.1, f"{y:.2f}", ha="center", va="bottom")

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved chart to {output_file}")
    else:
        plt.show()

    plt.close()


def create_comparison_chart(
    comparison: dict, title: str, output_file: str | None = None
) -> None:
    """
    Create a chart comparing baseline vs new results.

    Args:
        comparison: Comparison data
        title: Chart title
        output_file: Output file path
    """
    latency_metrics = comparison.get("metrics", {}).get("latency", {})
    if not latency_metrics:
        print(f"No latency metrics found in comparison data for {title}")
        return

    metrics = ["mean", "median", "p90", "p99"]
    baseline_values = [latency_metrics[m]["baseline"] for m in metrics]
    new_values = [latency_metrics[m]["new"] for m in metrics]

    x = range(len(metrics))
    width = 0.35

    plt.figure(figsize=(12, 7))
    plt.bar(
        [i - width / 2 for i in x],
        baseline_values,
        width,
        label="Baseline",
        color="royalblue",
    )
    plt.bar(
        [i + width / 2 for i in x], new_values, width, label="New", color="lightcoral"
    )

    plt.title(title)
    plt.ylabel("Latency (seconds)")
    plt.xticks(x, metrics)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add change percentage labels
    for i, metric in enumerate(metrics):
        change_pct = latency_metrics[metric]["change_pct"]
        color = "green" if change_pct <= 0 else "red"
        plt.text(
            i,
            max(baseline_values[i], new_values[i]) + 0.03,
            f"{change_pct:+.1f}%",
            ha="center",
            va="bottom",
            color=color,
            fontweight="bold",
        )

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved comparison chart to {output_file}")
    else:
        plt.show()

    plt.close()


def create_sustained_load_chart(
    result: dict, title: str, output_file: str | None = None
) -> None:
    """
    Create a chart showing performance degradation over time for a sustained load test.

    Args:
        result: Result data
        title: Chart title
        output_file: Output file path
    """
    # First look directly in metrics
    metrics = result.get("metrics", {})
    degradation = metrics.get("degradation", {})
    segments = degradation.get("segments", [])

    # If not found, check in the data structure
    if not segments:
        data = result.get("data", {})
        degradation = data.get("degradation", {})
        segments = degradation.get("segments", [])

    if not segments:
        print(f"No segment data found in sustained load test: {title}")
        return

    # Extract segment data
    segment_nums = []
    latencies = []

    for segment in segments:
        segment_nums.append(segment.get("segment", 0))
        latencies.append(segment.get("avg_latency", 0))

    # Create the chart
    plt.figure(figsize=(10, 6))
    plt.plot(segment_nums, latencies, marker="o", linestyle="-", color="red")

    # Add reference line for initial latency
    if latencies:
        initial_latency = latencies[0]
        plt.axhline(
            y=initial_latency,
            color="green",
            linestyle="--",
            label=f"Initial Latency ({initial_latency:.6f}s)",
        )

    plt.title(title)
    plt.xlabel("Time Segment")
    plt.ylabel("Average Latency (seconds)")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()

    # Calculate degradation percentage
    if len(latencies) >= MIN_SEGMENTS_FOR_DEGRADATION:
        initial = latencies[0]
        final = latencies[-1]
        degradation_pct = ((final / initial) - 1) * 100
        plt.annotate(
            f"Degradation: {degradation_pct:.1f}%",
            xy=(0.02, 0.95),
            xycoords="axes fraction",
            fontsize=12,
            bbox={
                "boxstyle": "round,pad=0.3",
                "fc": "white",
                "ec": "red",
                "alpha": 0.8,
            },
        )

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved chart to {output_file}")
    else:
        plt.show()

    plt.close()


def create_streaming_performance_chart(
    results: list[dict], title: str, output_file: str | None = None
) -> None:
    """
    Create a chart showing streaming performance metrics (TTFT and tokens/sec).

    Args:
        results: List of result data
        title: Chart title
        output_file: Output file path
    """
    # Setup data structures
    providers = []
    ttft_values = []
    tps_values = []  # tokens per second

    for result in results:
        metrics = result.get("metrics", {})

        provider = metrics.get("provider", "unknown")
        model = metrics.get("model", "unknown")
        label = f"{provider} ({model})"

        ttft = metrics.get("ttft", {}).get("avg", 0)
        tps = metrics.get("tokens_per_second", {}).get("avg", 0)

        if ttft == 0 and tps == 0:
            print(f"No streaming metrics found for {label}")
            continue

        providers.append(label)
        ttft_values.append(ttft)
        tps_values.append(tps)

    if not providers:
        print(f"No streaming data found for {title}")
        return

    # Create the chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # TTFT chart
    ax1.bar(providers, ttft_values, color="blue")
    ax1.set_title(f"Time to First Token (seconds): {title}")
    ax1.set_ylabel("Seconds")
    ax1.grid(axis="y", linestyle="--", alpha=0.7)

    # Add values on top of bars
    for i, v in enumerate(ttft_values):
        ax1.text(i, v + 0.01, f"{v:.4f}s", ha="center")

    # Tokens per second chart
    ax2.bar(providers, tps_values, color="green")
    ax2.set_title(f"Tokens per Second: {title}")
    ax2.set_ylabel("Tokens/sec")
    ax2.grid(axis="y", linestyle="--", alpha=0.7)

    # Add values on top of bars
    for i, v in enumerate(tps_values):
        ax2.text(i, v + 0.1, f"{v:.2f}", ha="center")

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved chart to {output_file}")
    else:
        plt.show()

    plt.close()


def compare_streaming_tests(baseline: dict, new: dict) -> dict:
    """
    Compare two streaming performance test results.

    Args:
        baseline: Baseline result
        new: New result

    Returns:
        Dictionary with comparison metrics
    """
    baseline_metrics = baseline.get("metrics", {})
    new_metrics = new.get("metrics", {})

    # Extract key metrics
    baseline_ttft = baseline_metrics.get("ttft", {}).get("avg", 0)
    new_ttft = new_metrics.get("ttft", {}).get("avg", 0)
    ttft_change = ((new_ttft / baseline_ttft) - 1) * 100 if baseline_ttft > 0 else 0

    baseline_tps = baseline_metrics.get("tokens_per_second", {}).get("avg", 0)
    new_tps = new_metrics.get("tokens_per_second", {}).get("avg", 0)
    tps_change = ((new_tps / baseline_tps) - 1) * 100 if baseline_tps > 0 else 0

    return {
        "ttft": {"baseline": baseline_ttft, "new": new_ttft, "change_pct": ttft_change},
        "tokens_per_second": {
            "baseline": baseline_tps,
            "new": new_tps,
            "change_pct": tps_change,
        },
    }


def compare_sustained_load_tests(
    baseline: dict, new: dict, output_file: str | None = None
) -> dict:
    """
    Compare two sustained load test results.

    Args:
        baseline: Baseline result
        new: New result
        output_file: Path to save comparison chart

    Returns:
        Dictionary with comparison metrics
    """
    baseline_data = baseline.get("data", {})
    new_data = new.get("data", {})

    # Extract key metrics
    baseline_throughput = baseline_data.get("throughput", 0)
    new_throughput = new_data.get("throughput", 0)
    throughput_change = (
        ((new_throughput / baseline_throughput) - 1) * 100
        if baseline_throughput > 0
        else 0
    )

    baseline_latency = baseline_data.get("latency_stats", {}).get("mean", 0)
    new_latency = new_data.get("latency_stats", {}).get("mean", 0)
    latency_change = (
        ((new_latency / baseline_latency) - 1) * 100 if baseline_latency > 0 else 0
    )

    baseline_degradation = baseline_data.get("degradation", {}).get("percent", 0)
    new_degradation = new_data.get("degradation", {}).get("percent", 0)
    degradation_change = new_degradation - baseline_degradation

    # Create comparison visualization
    plt.figure(figsize=(12, 8))

    # Plot throughput comparison
    plt.subplot(2, 2, 1)
    plt.bar(
        ["Baseline", "New"],
        [baseline_throughput, new_throughput],
        color=["blue", "orange"],
    )
    plt.title("Throughput (req/sec)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Plot latency comparison
    plt.subplot(2, 2, 2)
    plt.bar(
        ["Baseline", "New"], [baseline_latency, new_latency], color=["blue", "orange"]
    )
    plt.title("Average Latency (seconds)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Plot degradation comparison
    plt.subplot(2, 2, 3)
    plt.bar(
        ["Baseline", "New"],
        [baseline_degradation, new_degradation],
        color=["blue", "orange"],
    )
    plt.title("Performance Degradation (%)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Text summary
    plt.subplot(2, 2, 4)
    plt.axis("off")
    summary = (
        f"Throughput: {baseline_throughput:.2f} → {new_throughput:.2f} req/s ({throughput_change:+.1f}%)\n"
        f"Latency: {baseline_latency:.4f} → {new_latency:.4f}s ({latency_change:+.1f}%)\n"
        f"Degradation: {baseline_degradation:.1f}% → {new_degradation:.1f}% ({degradation_change:+.1f}%)"
    )
    plt.text(0.5, 0.5, summary, ha="center", va="center", fontsize=12)

    plt.suptitle("Sustained Load Test Comparison", fontsize=16)
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved sustained load comparison to {output_file}")

    plt.close()

    return {
        "throughput": {
            "baseline": baseline_throughput,
            "new": new_throughput,
            "change_pct": throughput_change,
        },
        "latency": {
            "baseline": baseline_latency,
            "new": new_latency,
            "change_pct": latency_change,
        },
        "degradation": {
            "baseline": baseline_degradation,
            "new": new_degradation,
            "change_pct": degradation_change,
        },
    }


def create_chat_completion_throughput_chart(
    results: list[dict], title: str, output_file: str | None = None
) -> None:
    """
    Create a chart comparing throughput for chat completion tests with different concurrent request values.

    Args:
        results: List of result data dictionaries
        title: Chart title
        output_file: Output file path
    """
    concurrent_requests = []
    throughputs = []
    success_rates = []
    labels = []

    for result in results:
        metrics = result.get("metrics", {})
        if not metrics:
            print(
                f"No stats found in results for {title} - {result.get('timestamp', 'unknown')}"
            )
            continue

        if "concurrent_requests" in metrics and "throughput" in metrics:
            concurrent_req = metrics["concurrent_requests"]
            throughput = metrics["throughput"]
            success_rate = metrics.get("success_rate", 0)
            timestamp = result.get("timestamp", "unknown")

            concurrent_requests.append(concurrent_req)
            throughputs.append(throughput)
            success_rates.append(success_rate)
            labels.append(f"{concurrent_req} ({timestamp})")

    if not concurrent_requests:
        print(f"No throughput data found for {title}")
        return

    # Setup the chart
    plt.figure(figsize=(12, 8))

    # Create a chart with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Plot throughput
    ax1.bar(labels, throughputs, color="blue")
    ax1.set_title(f"Throughput (Requests/sec): {title}")
    ax1.set_ylabel("Requests/sec")
    ax1.grid(axis="y", linestyle="--", alpha=0.7)

    # Add throughput values on top of the bars
    for i, v in enumerate(throughputs):
        ax1.text(i, v + 1, f"{v:.2f}", ha="center")

    # Plot success rate
    ax2.bar(labels, success_rates, color="green")
    ax2.set_title(f"Success Rate (%): {title}")
    ax2.set_ylabel("Success Rate (%)")
    ax2.set_ylim(0, 105)  # Set y-limit to 0-105% to leave room for labels
    ax2.grid(axis="y", linestyle="--", alpha=0.7)

    # Add success rate values on top of the bars
    for i, v in enumerate(success_rates):
        ax2.text(i, v + 2, f"{v:.1f}%", ha="center")

    # Adjust layout
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"Saved chart to {output_file}")
    else:
        plt.show()

    plt.close()


def encode_image_to_base64(image_path):
    """
    Encode an image file to base64 for embedding in HTML.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string with data URI prefix
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        print(f"Warning: Could not encode image {image_path}: {str(e)}")
        return ""


def create_simple_dashboard(output_dir, results_by_test):
    """Create a detailed HTML dashboard with tabs and categories"""
    dashboard_path = output_dir / "performance_dashboard.html"

    # Group tests by category
    latency_tests = []
    throughput_tests = []
    streaming_tests = []
    sustained_tests = []
    provider_tests = []

    for test_name in sorted(results_by_test.keys()):
        if "models_endpoint_throughput" in test_name:
            # Put models_endpoint_throughput tests in throughput category
            throughput_tests.append(test_name)
        elif "latency" in test_name and "throughput" not in test_name:
            # Add to latency tests, but provider_latency tests go to provider tab
            if "provider_latency" not in test_name:
                latency_tests.append(test_name)
            else:
                provider_tests.append(test_name)
        elif "throughput" in test_name:
            throughput_tests.append(test_name)
        elif "streaming" in test_name:
            streaming_tests.append(test_name)
        elif "sustained" in test_name:
            sustained_tests.append(test_name)
        elif "provider" in test_name:
            provider_tests.append(test_name)

    # Remove API key validation and models endpoint latency from provider tests if they're in latency tests
    provider_tests = [
        test
        for test in provider_tests
        if not (
            ("api_key_validation" in test or "models_endpoint_latency" in test)
            and test in latency_tests
        )
    ]

    # Generate HTML content
    html_content = (
        """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Forge API Performance Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                color: #333;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2, h3 {
                color: #2c3e50;
            }
            h1 {
                text-align: center;
                padding: 20px 0;
                margin: 0;
                background-color: #3498db;
                color: white;
                border-radius: 5px 5px 0 0;
            }
            .tab {
                overflow: hidden;
                border: 1px solid #ccc;
                background-color: #f1f1f1;
                border-radius: 5px 5px 0 0;
                margin-top: 20px;
            }
            .tab button {
                background-color: inherit;
                float: left;
                border: none;
                outline: none;
                cursor: pointer;
                padding: 14px 16px;
                transition: 0.3s;
                font-size: 16px;
            }
            .tab button:hover {
                background-color: #ddd;
            }
            .tab button.active {
                background-color: #3498db;
                color: white;
            }
            .tabcontent {
                display: none;
                padding: 20px;
                border: 1px solid #ccc;
                border-top: none;
                border-radius: 0 0 5px 5px;
                background-color: white;
            }
            .test-card {
                margin: 15px 0;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                background-color: white;
            }
            .metrics-table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 14px;
            }
            .metrics-table th, .metrics-table td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            .metrics-table th {
                background-color: #f2f2f2;
            }
            .metrics-table tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            .graph-container {
                text-align: center;
                margin: 20px 0;
            }
            .graph-container img {
                max-width: 100%;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                border-radius: 5px;
            }
            .summary-card {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .dashboard-date {
                text-align: center;
                margin-top: 10px;
                color: #7f8c8d;
            }
            .test-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                gap: 20px;
            }
            @media (max-width: 768px) {
                .test-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Forge API Performance Dashboard</h1>
            <div class="dashboard-date">Generated on """
        + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + """</div>

            <div class="summary-card">
                <h2>Summary</h2>
                <p>This dashboard presents performance test results for the Forge API, focusing on latency, throughput, streaming performance, and provider-specific metrics.</p>
                <p><strong>Test Categories:</strong></p>
                <ul>
                    <li><strong>Latency Tests:</strong> """
        + str(len(latency_tests))
        + """ tests measuring response time across different endpoints and models</li>
                    <li><strong>Throughput Tests:</strong> """
        + str(len(throughput_tests))
        + """ tests measuring request processing capacity</li>
                    <li><strong>Streaming Tests:</strong> """
        + str(len(streaming_tests))
        + """ tests measuring streaming performance metrics</li>
                    <li><strong>Sustained Load Tests:</strong> """
        + str(len(sustained_tests))
        + """ tests measuring performance under continuous load</li>
                    <li><strong>Provider Tests:</strong> """
        + str(len(provider_tests))
        + """ tests comparing different provider implementations</li>
                </ul>
                <p>Total Tests: """
        + str(
            sum(
                [
                    len(latency_tests),
                    len(throughput_tests),
                    len(streaming_tests),
                    len(sustained_tests),
                    len(provider_tests),
                ]
            )
        )
        + """</p>
            </div>

            <div class="tab">
                <button class="tablinks active" onclick="openTab(event, 'LatencyTab')">Latency Tests</button>
                <button class="tablinks" onclick="openTab(event, 'ThroughputTab')">Throughput Tests</button>
                <button class="tablinks" onclick="openTab(event, 'StreamingTab')">Streaming Tests</button>
                <button class="tablinks" onclick="openTab(event, 'SustainedTab')">Sustained Load Tests</button>
                <button class="tablinks" onclick="openTab(event, 'ProviderTab')">Provider Tests</button>
            </div>
    """
    )

    # Add Latency Tests Tab
    html_content += """
    <div id="LatencyTab" class="tabcontent" style="display: block;">
        <h2>Latency Tests</h2>
        <p>These tests measure the response time of various API endpoints under different conditions.</p>
        <div class="test-grid">
    """

    for test_name in latency_tests:
        if test_name not in results_by_test:
            continue

        results = results_by_test[test_name]
        if not results:
            continue

        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))
        latest_result = results[-1]

        # Find the latest image for this test
        img_filename = f"{test_name}_{latest_result.get('timestamp', 'unknown')}.png"

        metrics = latest_result.get("metrics", {})
        model = metrics.get("model", "N/A")
        stats = metrics.get("stats", {})
        latency_min = stats.get("min", 0)
        latency_max = stats.get("max", 0)
        latency_avg = stats.get("mean", 0)
        success_rate = metrics.get("success_rate", 0)

        html_content += f"""
        <div class="test-card">
            <h3>{test_name}</h3>
            <p><strong>Model:</strong> {model}</p>
            <table class="metrics-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Min Latency</td>
                    <td>{latency_min:.4f}s</td>
                </tr>
                <tr>
                    <td>Max Latency</td>
                    <td>{latency_max:.4f}s</td>
                </tr>
                <tr>
                    <td>Avg Latency</td>
                    <td>{latency_avg:.4f}s</td>
                </tr>
                <tr>
                    <td>Success Rate</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
            </table>
            <div class="graph-container">
                <img src="{img_filename}" alt="{test_name} graph">
            </div>
        </div>
        """

    html_content += """
        </div>
    </div>
    """

    # Add Throughput Tests Tab
    html_content += """
    <div id="ThroughputTab" class="tabcontent">
        <h2>Throughput Tests</h2>
        <p>These tests measure the request processing capacity of the API under different concurrency levels.</p>
        <div class="test-grid">
    """

    # Explicitly add models_endpoint_throughput tests first
    endpoint_throughput_levels = ["c1", "c5", "c10", "c25", "c50"]

    for c_level in endpoint_throughput_levels:
        test_name = f"models_endpoint_throughput_{c_level}"
        img_filename = (
            f"models_endpoint_throughput_{c_level}_concurrency_comparison.png"
        )

        # Check if we have this test in our results
        if test_name in results_by_test:
            results = results_by_test[test_name]
            if not results:
                continue

            # Sort by timestamp
            results.sort(key=lambda x: x.get("timestamp", ""))
            latest_result = results[-1]

            metrics = latest_result.get("metrics", {})
            concurrency = c_level[1:]  # Extract number from c1, c5, etc.
            success_rate = metrics.get("success_rate", 0)

            # Extract throughput value
            throughput_value = "N/A"
            if isinstance(
                metrics.get("throughput"), dict
            ) and "avg_req_per_sec" in metrics.get("throughput", {}):
                throughput_value = metrics["throughput"]["avg_req_per_sec"]
            elif isinstance(metrics.get("throughput"), int | float):
                throughput_value = metrics.get("throughput")

            html_content += f"""
            <div class="test-card">
                <h3>{test_name}</h3>
                <table class="metrics-table">
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                    <tr>
                        <td>Concurrency</td>
                        <td>{concurrency}</td>
                    </tr>
                    <tr>
                        <td>Throughput</td>
                        <td>{throughput_value if isinstance(throughput_value, str) else f"{throughput_value:.2f} req/s"}</td>
                    </tr>
                    <tr>
                        <td>Success Rate</td>
                        <td>{success_rate:.1f}%</td>
                    </tr>
                </table>
                <div class="graph-container">
                    <img src="{img_filename}" alt="{test_name} graph">
                </div>
            </div>
            """

    # Add the rest of the throughput tests
    for test_name in throughput_tests:
        # Skip models_endpoint_throughput tests as we've already handled them
        if any(
            f"models_endpoint_throughput_{c}" in test_name
            for c in endpoint_throughput_levels
        ):
            continue

        if test_name not in results_by_test:
            continue

        results = results_by_test[test_name]
        if not results:
            continue

        # Continue with the rest of the throughput test display code
        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))
        latest_result = results[-1]

        # Find the correct image for this test
        img_filename = None
        if "models_endpoint_throughput" in test_name:
            # Special handling for models_endpoint_throughput tests with concurrency in name
            img_filename = f"{test_name}_concurrency_comparison.png"
        elif "concurrency" in latest_result.get("metrics", {}):
            img_filename = f"{test_name}_concurrency_comparison.png"
        else:
            img_filename = f"{test_name}_comparison.png"

        metrics = latest_result.get("metrics", {})
        concurrency = (
            metrics.get("concurrency", "N/A")
            if "concurrency" in metrics
            else metrics.get("concurrent_requests", "N/A")
        )

        # For models_endpoint_throughput, extract concurrency from the test name if available
        if "models_endpoint_throughput" in test_name and isinstance(test_name, str):
            parts = test_name.split("_")
            for part in parts:
                if part.startswith("c") and part[1:].isdigit():
                    concurrency = part[1:]
                    break

        success_rate = metrics.get("success_rate", 0)

        # Extract throughput value
        throughput_value = "N/A"
        if isinstance(
            metrics.get("throughput"), dict
        ) and "avg_req_per_sec" in metrics.get("throughput", {}):
            throughput_value = metrics["throughput"]["avg_req_per_sec"]
        elif isinstance(metrics.get("throughput"), int | float):
            throughput_value = metrics.get("throughput")

        html_content += f"""
        <div class="test-card">
            <h3>{test_name}</h3>
            <table class="metrics-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Concurrency</td>
                    <td>{concurrency}</td>
                </tr>
                <tr>
                    <td>Throughput</td>
                    <td>{throughput_value if isinstance(throughput_value, str) else f"{throughput_value:.2f} req/s"}</td>
                </tr>
                <tr>
                    <td>Success Rate</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
            </table>
            <div class="graph-container">
        """

        # Check if the image file exists
        img_file = output_dir / img_filename
        if img_file.exists():
            html_content += f"""
                <img src="{img_filename}" alt="{test_name} graph">
            """
        elif "models_endpoint_throughput" in test_name:
            # Debug output
            print(f"Looking for image for {test_name}")
            print(f"Initial image path: {img_file}")

            # List all png files for models_endpoint_throughput
            all_throughput_files = list(
                output_dir.glob("models_endpoint_throughput_*.png")
            )
            print(
                f"Found {len(all_throughput_files)} models_endpoint_throughput png files"
            )

            # Extract concurrency level from test name
            concurrency_level = None
            if "_c" in test_name:
                parts = test_name.split("_c")
                if len(parts) > 1 and parts[1].isdigit():
                    concurrency_level = parts[1]

            # Try direct match with concurrency level
            if concurrency_level:
                direct_match = f"models_endpoint_throughput_c{concurrency_level}_concurrency_comparison.png"
                direct_match_file = output_dir / direct_match

                if direct_match_file.exists():
                    print(f"Found direct match: {direct_match}")
                    html_content += f"""
                        <img src="{direct_match}" alt="{test_name} graph">
                        """
                else:
                    # Try simple pattern with just concurrency
                    simple_match = f"models_endpoint_throughput_c{concurrency_level}_concurrency_comparison.png"
                    simple_match_file = output_dir / simple_match

                    if simple_match_file.exists():
                        print(f"Found simple match: {simple_match}")
                        html_content += f"""
                            <img src="{simple_match}" alt="{test_name} graph">
                            """
                    else:
                        # Look for any file with concurrency in the name
                        for file in all_throughput_files:
                            if f"c{concurrency_level}" in file.name:
                                print(
                                    f"Found file with c{concurrency_level}: {file.name}"
                                )
                                html_content += f"""
                                    <img src="{file.name}" alt="{test_name} graph">
                                    """
                                break
                        else:
                            html_content += f"""
                                <div style="border: 1px dashed #ddd; padding: 20px; text-align: center; background-color: #f8f9fa;">
                                    <h4>No visualization available</h4>
                                    <p>Looking for: {img_filename} or any file with c{concurrency_level}</p>
                                    <p>Concurrency: {concurrency}</p>
                                    <p>Throughput: {throughput_value if isinstance(throughput_value, str) else f"{throughput_value:.2f} req/s"}</p>
                                </div>
                                """
            else:
                # For any other models_endpoint_throughput test without clear concurrency level
                html_content += f"""
                    <div style="border: 1px dashed #ddd; padding: 20px; text-align: center; background-color: #f8f9fa;">
                        <h4>No visualization available</h4>
                        <p>Looking for: {img_filename}</p>
                        <p>Concurrency: {concurrency}</p>
                        <p>Throughput: {throughput_value if isinstance(throughput_value, str) else f"{throughput_value:.2f} req/s"}</p>
                    </div>
                    """
        else:
            html_content += f"""
                <div style="border: 1px dashed #ddd; padding: 20px; text-align: center; background-color: #f8f9fa;">
                    <h4>No visualization available</h4>
                    <p>Looking for: {img_filename}</p>
                    <p>Concurrency: {concurrency}</p>
                    <p>Throughput: {throughput_value if isinstance(throughput_value, str) else f"{throughput_value:.2f} req/s"}</p>
                </div>
                """

        html_content += """
            </div>
        </div>
        """
    html_content += """
        </div>
    </div>
    """

    # Add Streaming Tests Tab
    html_content += """
    <div id="StreamingTab" class="tabcontent">
        <h2>Streaming Tests</h2>
        <p>These tests measure the streaming performance of the API, including time to first token and token generation rate.</p>
        <div class="test-grid">
    """

    for test_name in streaming_tests:
        if test_name not in results_by_test:
            continue

        results = results_by_test[test_name]
        if not results:
            continue

        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))
        latest_result = results[-1]

        # Use the comparison image for streaming tests
        img_filename = f"{test_name}_comparison.png"

        metrics = latest_result.get("metrics", {})
        provider = metrics.get("provider", "N/A")
        model = metrics.get("model", "N/A")
        ttft_avg = metrics.get("ttft", {}).get("avg", 0)
        tps_avg = metrics.get("tokens_per_second", {}).get("avg", 0)
        success_rate = metrics.get("success_rate", 0)

        html_content += f"""
        <div class="test-card">
            <h3>{test_name}</h3>
            <p><strong>Provider:</strong> {provider}</p>
            <p><strong>Model:</strong> {model}</p>
            <table class="metrics-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Avg Time to First Token</td>
                    <td>{ttft_avg:.4f}s</td>
                </tr>
                <tr>
                    <td>Avg Tokens per Second</td>
                    <td>{tps_avg:.2f}</td>
                </tr>
                <tr>
                    <td>Success Rate</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
            </table>
            <div class="graph-container">
                <img src="{img_filename}" alt="{test_name} graph">
            </div>
        </div>
        """

    html_content += """
        </div>
    </div>
    """

    # Add Sustained Load Tests Tab
    html_content += """
    <div id="SustainedTab" class="tabcontent">
        <h2>Sustained Load Tests</h2>
        <p>These tests measure the API performance under sustained load over time, focusing on performance degradation patterns.</p>
        <div class="test-grid">
    """

    for test_name in sustained_tests:
        if test_name not in results_by_test:
            continue

        results = results_by_test[test_name]
        if not results:
            continue

        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))
        latest_result = results[-1]

        # Find the latest image for this test
        img_filename = f"{test_name}_{latest_result.get('timestamp', 'unknown')}.png"

        metrics = latest_result.get("metrics", {})
        model = metrics.get("model", "N/A")
        concurrency = metrics.get("concurrency", "N/A")
        duration = metrics.get("duration", "N/A")
        throughput = metrics.get("throughput", 0)
        success_rate = metrics.get("success_rate", 0)
        degradation_pct = metrics.get("degradation", {}).get("percent", 0)

        html_content += f"""
        <div class="test-card">
            <h3>{test_name}</h3>
            <p><strong>Model:</strong> {model}</p>
            <table class="metrics-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Concurrency</td>
                    <td>{concurrency}</td>
                </tr>
                <tr>
                    <td>Duration</td>
                    <td>{duration}s</td>
                </tr>
                <tr>
                    <td>Throughput</td>
                    <td>{throughput:.2f} req/s</td>
                </tr>
                <tr>
                    <td>Performance Degradation</td>
                    <td>{degradation_pct:.1f}%</td>
                </tr>
                <tr>
                    <td>Success Rate</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
            </table>
            <div class="graph-container">
                <img src="{img_filename}" alt="{test_name} graph">
            </div>
        </div>
        """

    html_content += """
        </div>
    </div>
    """

    # Add Provider Tests Tab
    html_content += """
    <div id="ProviderTab" class="tabcontent">
        <h2>Provider Tests</h2>
        <p>These tests compare the performance of different provider implementations.</p>
        <div class="test-grid">
    """

    for test_name in provider_tests:
        if test_name not in results_by_test:
            continue

        results = results_by_test[test_name]
        if not results:
            continue

        # Sort by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))
        latest_result = results[-1]
        timestamp = latest_result.get("timestamp", "unknown")

        # Get metrics
        metrics = latest_result.get("metrics", {})
        provider = metrics.get("provider", "N/A")
        model = metrics.get("model", "N/A")
        stats = metrics.get("stats", {})
        latency_avg = stats.get("mean", 0)
        success_rate = metrics.get("success_rate", 0)

        html_content += f"""
        <div class="test-card">
            <h3>{test_name}</h3>
            <p><strong>Provider:</strong> {provider}</p>
            <p><strong>Model:</strong> {model}</p>
            <table class="metrics-table">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Avg Latency</td>
                    <td>{latency_avg:.4f}s</td>
                </tr>
                <tr>
                    <td>Success Rate</td>
                    <td>{success_rate:.1f}%</td>
                </tr>
                <tr>
                    <td>Latest Test</td>
                    <td>{timestamp}</td>
                </tr>
            </table>
        """

        # Check if image exists
        img_file = output_dir / f"{test_name}_{timestamp}.png"
        if img_file.exists():
            html_content += f"""
            <div class="graph-container">
                <img src="{test_name}_{timestamp}.png" alt="{test_name} graph">
            </div>
            """
        else:
            # Display a placeholder with metrics
            html_content += f"""
            <div class="graph-container">
                <div style="border: 1px dashed #ddd; padding: 20px; text-align: center; background-color: #f8f9fa;">
                    <h4>No visualization available</h4>
                    <p>Key Metrics:</p>
                    <p>Average Latency: {latency_avg:.4f}s</p>
                    <p>Success Rate: {success_rate:.1f}%</p>
                </div>
            </div>
            """

        html_content += """
        </div>
        """

    html_content += """
        </div>
    </div>
    """

    # Add JavaScript for tab switching
    html_content += """
    <script>
    function openTab(evt, tabName) {
        var i, tabcontent, tablinks;
        tabcontent = document.getElementsByClassName("tabcontent");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none";
        }
        tablinks = document.getElementsByClassName("tablinks");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].className = tablinks[i].className.replace(" active", "");
        }
        document.getElementById(tabName).style.display = "block";
        evt.currentTarget.className += " active";
    }
    </script>
    </body>
    </html>
    """

    # Write HTML content to file
    with open(dashboard_path, "w") as f:
        f.write(html_content)

    print(f"Dashboard created at {dashboard_path}")
    return dashboard_path


def compare_specific_files(baseline_file, new_file, output_dir):
    """Compare two specific result files and generate comparison charts"""
    try:
        baseline = load_result(baseline_file)
        new = load_result(new_file)

        test_name = new.get("test_name", "comparison")
        comparison = compare_results(baseline, new)

        # Create comparison chart
        title = f"Performance Comparison: {test_name}"
        output_file = output_dir / f"{test_name}_comparison.png"
        create_comparison_chart(comparison, title, str(output_file))

        # Check for specific test types and create specialized charts
        if "streaming_performance" in test_name:
            output_file = output_dir / f"{test_name}_streaming_comparison.png"
            streaming_comparison = compare_streaming_tests(baseline, new)
            # Would need a specialized chart function here
            print(f"Streaming comparison results: {streaming_comparison}")

        elif "sustained_load_test" in test_name:
            output_file = output_dir / f"{test_name}_sustained_comparison.png"
            compare_sustained_load_tests(baseline, new, str(output_file))

        print(f"Comparison completed for {test_name}")

    except Exception as e:
        print(f"Error comparing files: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Analyze performance test results")
    parser.add_argument("--baseline", help="Baseline result file")
    parser.add_argument("--new", help="New result file to compare")
    parser.add_argument("--output", help="Output directory for charts")
    parser.add_argument(
        "--dashboard", action="store_true", help="Generate HTML dashboard"
    )

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = Path(args.output) if args.output else GRAPH_DIR
    output_dir.mkdir(exist_ok=True, parents=True)

    # Ensure graphs directory exists
    graphs_dir = output_dir
    graphs_dir.mkdir(exist_ok=True, parents=True)

    # If specific files are provided, compare them
    if args.baseline and args.new:
        compare_specific_files(args.baseline, args.new, output_dir)
        return

    # Otherwise, analyze all results in the results directory
    result_files = list(RESULTS_DIR.glob("**/*.json"))
    print(f"Found {len(result_files)} result files")

    # Group results by test
    results_by_test = {}
    for file_path in result_files:
        try:
            with open(file_path) as f:
                result = json.load(f)

            # Extract test name from the result or the filename
            test_name = result.get("test_name", None)
            if not test_name:
                # Try to get it from the filename
                filename = file_path.stem
                # Strip the timestamp from the end if present
                test_name = filename.rsplit("-", 1)[0] if "-" in filename else filename

            if test_name not in results_by_test:
                results_by_test[test_name] = []

            results_by_test[test_name].append(result)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True, parents=True)

    # Process each test group
    for test_name, results in results_by_test.items():
        print(f"Processing {test_name} ({len(results)} results)")

        if not results:
            continue

        # Sort results by timestamp
        results.sort(key=lambda x: x.get("timestamp", ""))

        try:
            if "chat_completion_latency" in test_name:
                # For latency tests
                for result in results:
                    title = f"{test_name} - {result.get('timestamp', 'unknown')}"
                    output_file = (
                        graphs_dir
                        / f"{test_name}_{result.get('timestamp', 'unknown')}.png"
                    )
                    create_latency_bar_chart(result, title, str(output_file))

            elif "chat_completion_throughput" in test_name:
                # For chat completion throughput tests
                title = f"Chat Completion Throughput: {test_name}"
                output_file = graphs_dir / f"{test_name}_comparison.png"
                create_chat_completion_throughput_chart(
                    results, title, str(output_file)
                )

            elif "throughput" in test_name:
                # Check if this is a concurrency-based throughput test
                has_concurrency = False
                for result in results:
                    if "concurrency" in result.get("metrics", {}):
                        has_concurrency = True
                        break

                if has_concurrency:
                    # For throughput tests, create comparison across concurrency levels
                    title = f"Throughput vs Concurrency: {test_name}"
                    output_file = graphs_dir / f"{test_name}_concurrency_comparison.png"
                    create_throughput_comparison_chart(results, title, str(output_file))
                else:
                    # Individual throughput tests
                    for result in results:
                        title = f"{test_name} - {result.get('timestamp', 'unknown')}"
                        output_file = (
                            graphs_dir
                            / f"{test_name}_{result.get('timestamp', 'unknown')}.png"
                        )
                        try:
                            create_latency_bar_chart(result, title, str(output_file))
                        except Exception as e:
                            print(f"Error creating chart for {title}: {str(e)}")

            elif "streaming_performance" in test_name:
                # For streaming performance tests
                title = f"Streaming Performance: {test_name}"
                output_file = graphs_dir / f"{test_name}_comparison.png"
                create_streaming_performance_chart(results, title, str(output_file))

            elif "sustained_load_test" in test_name:
                # Create charts for each sustained load test
                for result in results:
                    title = (
                        f"Sustained Load Test - {result.get('timestamp', 'unknown')}"
                    )
                    output_file = (
                        graphs_dir
                        / f"{test_name}_{result.get('timestamp', 'unknown')}.png"
                    )
                    create_sustained_load_chart(result, title, str(output_file))

                # Compare first and last test if multiple tests exist
                if len(results) >= MIN_RESULTS_FOR_COMPARISON:
                    baseline = results[0]
                    new = results[-1]
                    output_file = graphs_dir / f"{test_name}_comparison.png"
                    compare_sustained_load_tests(baseline, new, str(output_file))

            elif (
                "provider_latency" in test_name
                or "models_endpoint_latency" in test_name
                or "api_key_validation_latency" in test_name
            ):
                # For provider latency tests, create individual charts
                for result in results:
                    title = f"{test_name} - {result.get('timestamp', 'unknown')}"
                    output_file = (
                        graphs_dir
                        / f"{test_name}_{result.get('timestamp', 'unknown')}.png"
                    )
                    create_latency_bar_chart(result, title, str(output_file))

                # Also create comparison if there are multiple results
                if len(results) >= MIN_RESULTS_FOR_COMPARISON:
                    baseline = results[0]
                    new = results[-1]
                    comparison = compare_results(baseline, new)

                    title = f"Performance Change: {test_name}"
                    output_file = graphs_dir / f"{test_name}_comparison.png"
                    create_comparison_chart(comparison, title, str(output_file))

            elif "provider_chat_completion_performance" in test_name:
                # Special handling for provider chat completion performance comparison
                for result in results:
                    timestamp = result.get("timestamp", "unknown")
                    metrics = result.get("metrics", {})

                    if not metrics:
                        print(
                            f"No metrics found in provider_chat_completion_performance - {timestamp}"
                        )
                        continue

                    # Create a chart comparing providers
                    providers = []
                    latencies = []
                    success_rates = []

                    # Extract data for each provider
                    for provider, provider_data in metrics.items():
                        if not isinstance(provider_data, dict):
                            continue

                        providers.append(provider)
                        stats = provider_data.get("stats", {})
                        latencies.append(stats.get("mean", 0))
                        success_rates.append(provider_data.get("success_rate", 0))

                    if not providers:
                        print(
                            f"No provider data found in provider_chat_completion_performance - {timestamp}"
                        )
                        continue

                    # Create a chart
                    plt.figure(figsize=(12, 8))

                    # Plot latency comparison
                    ax1 = plt.subplot(2, 1, 1)
                    bars = ax1.bar(providers, latencies, color="skyblue")
                    ax1.set_title(
                        f"Provider Chat Completion Latency Comparison - {timestamp}"
                    )
                    ax1.set_ylabel("Latency (seconds)")
                    ax1.grid(axis="y", linestyle="--", alpha=0.7)

                    # Add value labels
                    for bar in bars:
                        height = bar.get_height()
                        ax1.text(
                            bar.get_x() + bar.get_width() / 2,
                            height + 0.005,
                            f"{height:.4f}s",
                            ha="center",
                            va="bottom",
                        )

                    # Plot success rate comparison
                    ax2 = plt.subplot(2, 1, 2)
                    bars = ax2.bar(providers, success_rates, color="lightgreen")
                    ax2.set_title(
                        f"Provider Chat Completion Success Rate - {timestamp}"
                    )
                    ax2.set_ylabel("Success Rate (%)")
                    ax2.set_ylim(
                        0, 105
                    )  # Set y-limit to 0-105% to leave room for labels
                    ax2.grid(axis="y", linestyle="--", alpha=0.7)

                    # Add value labels
                    for bar in bars:
                        height = bar.get_height()
                        ax2.text(
                            bar.get_x() + bar.get_width() / 2,
                            height + 2,
                            f"{height:.1f}%",
                            ha="center",
                            va="bottom",
                        )

                    plt.tight_layout()

                    # Save the chart
                    output_file = graphs_dir / f"{test_name}_{timestamp}.png"
                    plt.savefig(output_file, dpi=300, bbox_inches="tight")
                    print(f"Saved provider comparison chart to {output_file}")
                    plt.close()

            elif len(results) >= MIN_RESULTS_FOR_COMPARISON:
                # For tests with multiple results, compare first and last
                try:
                    baseline = results[0]
                    new = results[-1]
                    comparison = compare_results(baseline, new)

                    title = f"Performance Change: {test_name}"
                    output_file = graphs_dir / f"{test_name}_comparison.png"
                    create_comparison_chart(comparison, title, str(output_file))
                except Exception as e:
                    print(f"Error creating comparison chart for {test_name}: {str(e)}")
        except Exception as e:
            print(f"Error processing {test_name}: {str(e)}")

    # Generate dashboard if requested
    if args.dashboard:
        if output_dir.is_dir():
            dashboard_path = create_simple_dashboard(output_dir, results_by_test)
            print(f"Dashboard created at {dashboard_path}")

            # Open dashboard in default browser
            try:
                import webbrowser

                webbrowser.open(f"file://{dashboard_path}")
            except Exception as e:
                print(f"Error opening dashboard: {str(e)}")
        else:
            print(f"Output directory {output_dir} does not exist")


if __name__ == "__main__":
    main()
