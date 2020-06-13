#!/bin/bash

CUR_DIR=$(pwd)

RESOURCES_DIR=${RESOURCES_DIR:-${CUR_DIR}/data/resources/}
DB_HOST=${DB_HOST:-localhost}

python -c 'import plynx.bin; plynx.bin.main()' worker -vvv \
    -e k8s-bash-jinja2-operation \
    -e k8s-python-node-operation \
    -e basic-bash-jinja2-operation \
    --db-host ${DB_HOST} \
    --storage-prefix ${RESOURCES_DIR}
