#!/bin/bash

docker exec -it $(docker ps | grep front | cut -f1 -d " ") sh
