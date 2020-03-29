#!/bin/bash

set -e

# watchmedo auto-restart --recursive --pattern="*.py" --directory="/app" -- python -m plynx.plugins.executors.test_dag
# scripts/test_00_sum.py

coverage run -m pytest plynx

echo "Coverage:"
coverage report -m
