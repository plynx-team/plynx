#!/bin/bash

set -e

source ./scripts/build_images.sh

docker-compose -f ./docker/compose-integration/docker-compose.yml up --abort-on-container-exit --scale workers=5