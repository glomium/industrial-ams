#!/bin/bash

set -e

_term() {
  echo "entrypoint.sh caught SIGTERM signal! Sending SIGTERM to $child"
  kill -TERM "$child"
  wait "$child"
  curl --verbose --request PUT --data-binary @.coverage http://$IAMS_RUNTESTS:8000
}

if [ -z "$IAMS_RUNTESTS" ]
then
    exec python3 $@
else
    trap _term SIGTERM
    coverage run $@ &
    child=$!
    wait "$child"
fi
