#!/bin/bash

docker build --rm -t khaxis/plynx:base    -f docker/base/Dockerfile    .
docker build --rm -t khaxis/plynx:backend -f docker/backend/Dockerfile .
docker build --rm -t khaxis/plynx:master  -f docker/master/Dockerfile  .
docker build --rm -t khaxis/plynx:worker  -f docker/worker/Dockerfile  .
docker build --rm -t khaxis/plynx:test    -f docker/test/Dockerfile    .
docker build --rm -t khaxis/plynx:ui      -f docker/ui/Dockerfile      .
