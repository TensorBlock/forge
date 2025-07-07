#! /bin/bash -xe
uv run pytest -vv tests/unit_tests --cov=app --cov-report=xml
