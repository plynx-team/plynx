#!/bin/bash

docker exec -it $(docker ps | grep mongo | cut -f1 -d " ") mongo
