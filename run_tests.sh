#!/bin/sh

set -e

# TODO this can be removed, when a fallback for connection failures to cfssl and arangodb are implemented
echo "wait 10s for services to bootup"
sleep 10

echo "run static tests"
doc8 iams examples
flake8 iams examples

echo "run unit tests"
mkdir coverage
COVERAGE_FILE=coverage/unit coverage run setup.py test

echo "start server"
COVERAGE_FILE=coverage/server coverage run -m iams.server --simulation --namespace test cfssl:8888 &

echo "wait 5s for server to bootup"
sleep 5

echo "run simulation"
# TODO not running
# COVERAGE_FILE=coverage/simulation coverage run -m iams.simulation -d examples/simulation/simulation.yaml 127.0.0.1:80

echo "stop server"
COVERAGE_FILE=coverage/stop coverage run -m iams.stop

# wait for server process to shutdown
wait

jobs

echo "collect coverages"
coverage combine coverage/*
coverage report
