#!/bin/sh

set -e

echo "run static tests"
doc8 iams examples
flake8 iams examples

echo "run unit tests"
COVERAGE_FILE=coverage/unit coverage run setup.py test

echo "start server"
COVERAGE_FILE=coverage/server coverage run -m iams.server -d --simulation --namespace test cfssl:8888 &

echo "wait 5s for server to bootup"
sleep 5

echo "run simulation"
COVERAGE_FILE=coverage/simulation coverage run -m iams.simulation -d -t 600 examples/simulation/simulation.yaml 127.0.0.1:80

echo "stop server"
COVERAGE_FILE=coverage/stop coverage run -m iams.stop

# wait for server process to shutdown
wait

jobs

echo "collect coverage reports from agents"
sleep 10
wget tasks.coverage:8000 -O coverage/agents

echo "collect coverages"
coverage combine coverage/*
cp .coverage coverage/combined
coverage report
