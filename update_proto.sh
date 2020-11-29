#!/bin/bash

export CONTAINER=`docker create iams-test:local`
docker cp $CONTAINER:/usr/src/app/iams/proto - > dist.tar
docker rm -v $CONTAINER
rm -rf iams/proto
tar -C iams -xf dist.tar
rm dist.tar
