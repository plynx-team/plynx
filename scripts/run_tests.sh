#!/bin/bash
set -e

coverage run -m pytest
echo "Coverage:"
coverage report -m
