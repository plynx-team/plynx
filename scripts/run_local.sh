#!/bin/bash

set -e

PLYNX_IMAGES="base backend master worker ui"

source ./scripts/build_images.sh

docker-compose -f ./docker-compose.yml up --abort-on-container-exit --scale workers=5 --scale test=0
