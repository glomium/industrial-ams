FROM alpine:3.10.3
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
# base alpine template

ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
RUN apk add --no-cache python3
# base python template

COPY setup.py setup.cfg requirements.txt ./

RUN apk add --no-cache openssl-dev libffi-dev libstdc++ \
 && apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements.txt \
 && apk del build-dependencies

COPY iams ./iams
RUN pip3 install .

ENTRYPOINT ["iams-server"]
