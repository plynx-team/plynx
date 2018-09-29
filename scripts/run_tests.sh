#!/bin/bash

set -e

source ./scripts/build_images.sh

docker-compose -f tests/integration/docker-compose.yml up --abort-on-container-exit --scale workers=5