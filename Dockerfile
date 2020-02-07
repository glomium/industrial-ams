ARG ALPINE=latest
FROM alpine:$ALPINE as basestage

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

COPY examples ./examples

# run static tests
RUN doc8 iams examples && flake8 iams examples

# run unit tests
RUN coverage run setup.py test
# TODO copy coverage results

# build wheel package
RUN python3 setup.py bdist_wheel && mv dist/iams-*-py3-none-any.whl iams-build-py3-none-any.whl

# === build stage =============================================================
FROM basestage as build
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
ENV PYTHONUNBUFFERED=1

COPY --from=test /usr/src/app/iams-build-py3-none-any.whl /tmp/iams-build-py3-none-any.whl
RUN pip3 install --no-index /tmp/iams-build-py3-none-any.whl && rm /tmp/requirements.txt
# TODO delete iams-build-py3-none-any.whl (when there is a official release on pypi)
# RUN pip3 install --no-index /tmp/iams-build-py3-none-any.whl && rm /tmp/iams-build-py3-none-any.whl /tmp/requirements.txt

ENTRYPOINT ["/usr/bin/iams-server"]
