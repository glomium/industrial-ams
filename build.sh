#!/bin/sh

set -e

export ALPINE=3.11.3
export REGISTRY=registry:5000

docker pull $REGISTRY/iams:$ALPINE || true
docker build --build-arg ALPINE=$ALPINE --cache-from iams-base:latest --target basestage -t iams-base:latest .
docker build --build-arg ALPINE=$ALPINE --cache-from iams-base:latest --cache-from iams-test:latest --target test -t iams-test:latest .
docker build --build-arg ALPINE=$ALPINE --cache-from iams-base:latest --cache-from iams-test:latest --cache-from iams-build:latest --cache-from $REGISTRY/iams:$ALPINE -t $REGISTRY/iams:latest -t $REGISTRY/iams:$ALPINE .
docker push $REGISTRY/iams:$ALPINE
docker push $REGISTRY/iams:latest
