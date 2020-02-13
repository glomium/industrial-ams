#!/bin/sh

set -e

docker build -f Dockerfile_source -t example_source:latest .
docker build -f Dockerfile_sink -t example_sink:latest .
docker build -f Dockerfile_vehicle -t example_vehicle:latest .
