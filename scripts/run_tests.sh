#!/bin/bash
set -e
set -x

# Run pytest
pytest plynx

# Run simple workflow

# TODO
# python -c "import plynx.bin; plynx.bin.main()" exec -f test_node.json --storage-prefix /tmp/data

echo "Tests passed"
