FROM alpine:3.10.3
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# base alpine template

ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
RUN apk add --no-cache python3
# base python template

COPY setup.py setup.cfg requirements.txt ./
COPY iams ./iams

RUN apk add --no-cache libstdc++ \
 && apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements.txt \
 && pip3 install . \
 && apk del build-dependencies

ENTRYPOINT ["iams-server"]
