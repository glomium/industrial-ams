# vim:set ft=dockerfile:
ARG BASEIMAGE=ubuntu:rolling
FROM $BASEIMAGE as basestage

MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C
ENV PYTHONUNBUFFERED=1

COPY dist/iams-*-py3-none-any.whl /tmp/

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    python3 \
    python3-pip \
&& pip3 install /tmp/iams-*-py3-none-any.whl \
&& apt-get clean \
&& rm -rf /tmp/ /var/lib/apt/lists/*

WORKDIR /usr/src/app

ENTRYPOINT ["/usr/local/bin/iams-server"]
