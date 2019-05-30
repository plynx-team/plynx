#!/bin/bash

set -e

PLYNX_IMAGES="base backend master worker test"

source ./scripts/build_images.sh

docker-compose -f ./docker/compose-integration/docker-compose.yml up --abort-on-container-exit --scale workers=5 --scale frontend=0
