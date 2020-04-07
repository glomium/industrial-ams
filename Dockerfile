ARG UBUNTU=rolling
FROM ubuntu:$UBUNTU as basestage

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    build-essential \
    curl \
    python3 \
    python3-cryptography \
    python3-dev \
    python3-grpc-tools \
    python3-grpcio \
    python3-pip \
    python3-protobuf \
    python3-requests \
    python3-setuptools \
    python3-yaml \
&& pip3 install --no-cache-dir coverage docker python-arango \
&& apt-get remove --purge --autoremove -y -q \
    build-essential \
    python3-dev \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*
# curl is needed to upload coverage reports via ftp
# coverage is added for "faster" integration tests - where we run simulations with test-coverage
# grpc-tools are added to compile protofiles to python
# installing "python3-docker" via apt delivers on 19.10 an old version not working with the framework

# === test stage ==============================================================
FROM basestage as test
WORKDIR /usr/src/app

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    build-essential \
    python3-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY requirements/dev.txt requirements/test.txt ./
RUN pip3 install --no-cache-dir -r dev.txt -r test.txt

COPY LICENSE setup.py setup.cfg .coveragerc run_tests.sh ./
COPY iams ./iams
COPY proto ./proto

RUN mkdir -p iams/proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto proto/framework.proto proto/market.proto proto/simulation.proto \
 && sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py

COPY examples ./examples

RUN doc8 iams examples
RUN flake8 iams examples

# build wheel package
RUN python3 setup.py bdist_wheel  # && mv dist/iams-*-py3-none-any.whl iams-build-py3-none-any.whl

ENTRYPOINT ["/usr/local/bin/coverage", "run", "-m", "iams-server"]

# === build stage =============================================================
FROM basestage as build

COPY --from=test /usr/src/app/dist/iams-*-py3-none-any.whl /tmp/

# TODO delete iams-build-py3-none-any.whl (when there is a official release on pypi)
RUN pip3 install --no-index /tmp/iams-*-py3-none-any.whl

MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
ENTRYPOINT ["/usr/local/bin/iams-server"]
