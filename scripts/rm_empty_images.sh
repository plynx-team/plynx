#!/bin/bash

docker images | sed 's/  */ /g' | awk 'BEGIN{FS=OFS=" "} $2=="<none>"{print $3}' | xargs docker rmi -f