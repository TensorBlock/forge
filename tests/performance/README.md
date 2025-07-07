# Forge Performance Tests

This directory contains performance tests for evaluating the Forge middleware service's performance characteristics.

## Overview

These tests measure key performance metrics such as:

- Response latency (p50, p90, p99)
- Throughput (requests per second)
- Scalability under varying loads
- Resource utilization
- Provider-specific performance metrics

Performance tests use the mock provider by default to ensure consistent and reproducible results without external dependencies.

## Prerequisites

To run these tests, you need:

1. A running instance of Forge
2. Python packages:
   - locust
   - pytest
   - pytest-benchmark
   - aiohttp
   - pandas (for results analysis)
   - matplotlib (for visualizations)

Install performance testing dependencies:

```bash
pip install locust pytest pytest-benchmark aiohttp pandas matplotlib
```

## Usage

### Single-run benchmarks:

```bash
# Run all performance tests
pytest tests/performance/

# Run specific performance test category
pytest tests/performance/test_latency.py
pytest tests/performance/test_throughput.py
pytest tests/performance/test_providers.py
```

### Load testing with Locust:

```bash
# Start Locust web interface
cd tests/performance
locust -f locustfile.py

# Run headless with 10 users, spawn rate of 1 user/sec, for 1 minute
locust -f locustfile.py --headless -u 10 -r 1 --run-time 1m
```

## About Mock Providers

Performance tests use mock providers rather than real API calls to:

- Eliminate external dependencies for consistent results
- Avoid rate limits and costs associated with real API calls
- Ensure reproducible test results
- Provide consistent response patterns and timing

This approach focuses on measuring Forge's own performance characteristics rather than the performance of external services.

## Baseline Results

The baseline performance results are stored in `baseline_results/` and represent reference numbers for comparing future changes.

## Output Analysis

Test results are saved to:
- JSON reports in `results/json/`
- CSV files in `results/csv/`
- Graphs in `results/graphs/`

Use the analysis utilities to compare results:

```bash
# Compare specific test runs
python tests/performance/analyze_results.py --baseline baseline_results/latest.json --new results/json/new_run.json

# Generate charts for all test results
python tests/performance/analyze_results.py

# Generate an interactive HTML dashboard with all test results
python tests/performance/analyze_results.py --dashboard
```

The HTML dashboard provides a comprehensive view of all performance test results in a single page with:
- Interactive tabs for different test categories
- Visual representations of all metrics
- Summary statistics for each test
- Test results grouped by type (latency, throughput, streaming, etc.)

After generating the dashboard, open it in any web browser:
```bash
# On macOS
open tests/performance/results/graphs/performance_dashboard.html

# On Linux
xdg-open tests/performance/results/graphs/performance_dashboard.html

# On Windows
start tests/performance/results/graphs/performance_dashboard.html
```

## Interpreting Results

When evaluating performance changes:
- Latency: Lower is better
- Throughput: Higher is better
- Error rate: Should remain at or near 0%
