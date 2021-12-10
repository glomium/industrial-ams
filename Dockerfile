# vim:set ft=dockerfile:
ARG BASEIMAGE=ubuntu:rolling
FROM $BASEIMAGE as basestage

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C

COPY requirements.txt /requirements.txt
RUN apt-get update && apt-get install --no-install-recommends -y -q \
    build-essential \
    curl \
    python3 \
    python3-dev \
    python3-pip \
    python3-setuptools \
&& pip3 install -U --no-cache-dir -r /requirements.txt  \
&& apt-get remove --purge --autoremove -y -q \
    build-essential \
    python3-dev \
&& apt-get clean \
&& rm -rf /requirements.txt /var/lib/apt/lists/*
# curl is needed to upload coverage reports via ftp

# === test stage ==============================================================
FROM basestage as test
WORKDIR /usr/src/app

ENV DEBIAN_FRONTEND noninteractive
ENV LANG en_US.utf8

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    wget \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

COPY requirements/dev.txt requirements/test.txt ./
RUN pip3 install --no-cache-dir -r dev.txt -r test.txt

COPY LICENSE setup.py setup.cfg .coveragerc .pylintrc ./
COPY proto ./proto
COPY iams ./iams

RUN mkdir -p iams/proto \
 && python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto \
    proto/agent.proto \
    proto/ca.proto \
    proto/df.proto \
    proto/framework.proto \
    proto/market.proto \
 && sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py \
 && doc8 iams \
 && flake8 iams \
 && pylint iams \
 && python3 -m unittest

# build wheel package
RUN python3 setup.py bdist_wheel

# === build stage =============================================================
FROM basestage as build

COPY --from=test /usr/src/app/dist/iams-*-py3-none-any.whl /tmp/

# TODO delete iams-build-py3-none-any.whl (when there is a official release on pypi)
RUN pip3 install --no-index /tmp/iams-*-py3-none-any.whl && rm -rf /tmp/*

MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
ENTRYPOINT ["/usr/local/bin/iams-server"]
