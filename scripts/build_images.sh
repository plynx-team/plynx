#!/bin/bash

set -e

PLYNX_IMAGES=${PLYNX_IMAGES:="backend ui ui_dev"}

source ./scripts/version.sh;
VERSION=$(plynx_version);


for IMAGE in ${PLYNX_IMAGES}; do
  docker build --rm -t plynxteam/${IMAGE}:${VERSION} -f docker/${IMAGE}/Dockerfile . ;
  docker tag plynxteam/${IMAGE}:${VERSION} plynxteam/${IMAGE}:latest;
done
