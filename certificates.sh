#!/bin/sh

mkdir -p secrets

# create new private key
openssl genrsa -out secrets/ca.key 8192

# create certificate for private key (which is 100 years valid)
openssl req -x509 -new -SHA384 -key secrets/ca.key -out secrets/ca.crt -days 36525

# create secrets for envoy
echo "crt" | docker secret create -l iams.certificates.crt=envoy envoy.crt -
echo "key" | docker secret create -l iams.certificates.key=envoy envoy.key -
