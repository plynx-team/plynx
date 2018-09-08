#!/bin/bash

docker build -t khaxis/plynx:base -f docker/base/Dockerfile .
docker build -t khaxis/plynx:worker -f docker/worker/Dockerfile .
