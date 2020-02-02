#!/bin/sh

set -e

export REGISTRY=registry:5000

docker pull $REGISTRY/iams:latest || true
docker build --cache-from iams-base:latest --target basestage -t iams-base:latest .
docker build --cache-from iams-base:latest --cache-from iams-test:latest --target test -t iams-test:latest .
docker build --cache-from iams-base:latest --cache-from iams-test:latest --cache-from iams-build:latest --cache-from $REGISTRY/iams:latest -t $REGISTRY/iams:latest .
docker push $REGISTRY/iams:latest
