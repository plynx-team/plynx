#!/bin/bash

set -e

echo "TODO: check status of backend instead of sleeping"
sleep 2

./scripts/test_00_sum.py --endpoint $PLYNX_ENDPOINT --data-path ./data_00
