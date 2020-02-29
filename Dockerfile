ARG UBUNTU=rolling
FROM ubuntu:$UBUNTU as basestage

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    python3 \
    python3-cryptography \
    python3-grpcio \
    python3-pip \
    python3-protobuf \
    python3-requests \
    python3-setuptools \
    python3-yaml \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# installing "python3-docker" via apt delivers on 19.10 an old version not working with the framework
RUN pip3 install --no-cache-dir docker

# === test stage ==============================================================
FROM basestage as test
WORKDIR /usr/src/app

COPY requirements/dev.txt requirements/test.txt ./
RUN pip3 install --no-cache-dir -r dev.txt -r test.txt

COPY LICENSE setup.py setup.cfg .coveragerc ./
COPY iams ./iams
COPY proto ./proto

RUN mkdir -p iams/proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/framework.proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/simulation.proto \
 && sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py

COPY examples ./examples

# run static tests
RUN doc8 iams examples && flake8 iams examples

# run unit tests
RUN coverage run setup.py test && coverage report
# TODO copy coverage results

# build wheel package
RUN python3 setup.py bdist_wheel  # && mv dist/iams-*-py3-none-any.whl iams-build-py3-none-any.whl

# === build stage =============================================================
FROM basestage as build

COPY --from=test /usr/src/app/dist/iams-*-py3-none-any.whl /tmp/

# TODO delete iams-build-py3-none-any.whl (when there is a official release on pypi)
RUN pip3 install --no-index /tmp/iams-*-py3-none-any.whl

MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
ENTRYPOINT ["/usr/local/bin/iams-server"]
