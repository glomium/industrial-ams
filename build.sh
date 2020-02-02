#!/bin/sh

set -e

export REGISTRY=registry:5000

docker pull $REGISTRY/iams:latest || true
docker build --cache-from $REGISTRY/iams:latest -t $REGISTRY/iams:latest .
docker push $REGISTRY/iams:latest
