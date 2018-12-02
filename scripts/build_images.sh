#!/bin/bash

set -e

source ./scripts/version.sh

export VERSION=$(plynx-version)
export IMAGES="base backend master worker test ui"

for IMAGE in ${IMAGES}; do
  docker build --rm -t khaxis/plynx:${IMAGE} -f docker/${IMAGE}/Dockerfile . ;
  echo -------------
  echo $VERSION
  docker tag khaxis/plynx:${IMAGE} khaxis/plynx_${VERSION}:${IMAGE};
done
