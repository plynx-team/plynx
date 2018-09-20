#!/bin/bash

docker build -t khaxis/plynx:base -f docker/base/Dockerfile .
docker build -t khaxis/plynx:backend -f docker/backend/Dockerfile .
docker build -t khaxis/plynx:master -f docker/master/Dockerfile .
docker build -t khaxis/plynx:worker -f docker/worker/Dockerfile .
docker build -t khaxis/plynx:test -f docker/test/Dockerfile .
