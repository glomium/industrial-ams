FROM alpine:3.11.3 as basestage

WORKDIR /usr/src/app
RUN apk add --no-cache python3

COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache openssl-dev libffi-dev libstdc++ \
 && apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r /tmp/requirements.txt \
 && apk del build-dependencies

# === test stage ==============================================================
FROM basestage as test

COPY requirements-dev.txt requirements-test.txt ./
RUN apk add --no-cache \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements-dev.txt -r requirements-test.txt

COPY LICENSE setup.py setup.cfg ./
COPY iams ./iams
COPY proto ./proto

# create protofiles
RUN mkdir -p iams/proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/framework.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/simulation.proto \
 && sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py

# run static tests
RUN doc8 iams && flake8 iams

# run unit tests
RUN coverage run setup.py test
# TODO copy coverage results

# build wheel package
RUN python3 setup.py bdist_wheel && mv dist/iams-*-py3-none-any.whl iams-build-py3-none-any.whl

# === build stage =============================================================
FROM basestage as build
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>

COPY --from=test /usr/src/app/iams-build-py3-none-any.whl /tmp/iams-build-py3-none-any.whl
RUN pip3 install --no-index /tmp/iams-build-py3-none-any.whl && rm /tmp/iams-build-py3-none-any.whl /tmp/requirements.txt

ENTRYPOINT ["/usr/bin/iams-server"]
