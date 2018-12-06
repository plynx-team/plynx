#!/bin/bash

set -e

source ./scripts/version.sh

VERSION=$(plynx-version)
PLYNX_IMAGES=${PLYNX_IMAGES:="base backend master worker test ui"}

for IMAGE in ${PLYNX_IMAGES}; do
  docker build --rm -t khaxis/plynx:${IMAGE} -f docker/${IMAGE}/Dockerfile . ;
  docker tag khaxis/plynx:${IMAGE} khaxis/plynx_${VERSION}:${IMAGE};
done
