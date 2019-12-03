FROM alpine:3.10.3
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
RUN apk add --no-cache ca-certificates
# base alpine template

ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app
RUN apk add --no-cache python3
# base python template

COPY requirements.txt ./requirements.txt
RUN apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements.txt \
 && apk del build-dependencies

# COPY iams ./iams
# COPY run.py ./run.py

# RUN doc8 run.py && flake8 run.py

CMD ["python3", "run.py", "-d"]
