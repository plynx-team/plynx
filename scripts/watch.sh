#!/bin/bash
set -e

watchmedo auto-restart --recursive --pattern="*.py" --directory="/app/plynx" -- bash -c " \
    python -c 'import plynx.bin; plynx.bin.main()' make-operations-meta --collection-module plynx.demo.COLLECTION -o /app/nodes.json && \
    python -c 'import plynx.bin; plynx.bin.main()' ${PLYNX_MODE} -vvv \
"
