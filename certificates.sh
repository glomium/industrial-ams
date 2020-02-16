#!/bin/sh

# create secrets for envoy
echo "crt" | docker secret create -l iams.certificates.crt=envoy envoy.crt -
echo "key" | docker secret create -l iams.certificates.key=envoy envoy.key -
