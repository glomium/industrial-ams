FROM alpine:3.10.3
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# base alpine template

ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
RUN apk add --no-cache python3
# base python template

COPY requirements.txt requirements-dev.txt ./

RUN apk add --no-cache openssl-dev libffi-dev libstdc++ \
 && apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements-dev.txt \
 && pip3 install --no-cache-dir -r requirements.txt \
 && apk del build-dependencies

COPY LICENSE setup.py setup.cfg ./
COPY iams ./iams
COPY proto ./proto
RUN mkdir -p iams/proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/framework.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/simulation.proto \
 && sed -i -E 's/^import.*_pb2/from . \\0/' iams/proto/*.py \
 && pip3 install .

ENTRYPOINT ["iams-server"]
