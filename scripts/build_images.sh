#!/bin/bash

set -e

PLYNX_IMAGES=${PLYNX_IMAGES:="base ui ui_dev"}

for IMAGE in ${PLYNX_IMAGES}; do
  docker build --rm -t khaxis/plynx:${IMAGE} -f docker/${IMAGE}/Dockerfile . ;
done

if [ ${TAG_VERSION} ]; then
  source ./scripts/version.sh;
  VERSION=$(plynx_version);

  for IMAGE in ${PLYNX_IMAGES}; do
    docker tag khaxis/plynx:${IMAGE} khaxis/plynx_${VERSION}:${IMAGE};
  done
fi
