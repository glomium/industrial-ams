FROM alpine:3.10.3
MAINTAINER Sebastian Braun <sebastian.braun@fh-aachen.de>
RUN apk add --no-cache ca-certificates
# base alpine template

# RUN apk add --no-cache
COPY requirements.txt ./requirements.txt

RUN apk add --no-cache --virtual build-dependencies \
    python3-dev \
    build-base \
 && pip3 install --no-cache-dir -r requirements.txt \
 && apk del build-dependencies

# COPY agent ./agent
# COPY ams ./ams

COPY docker/ams/run_control.py ./run.py

RUN doc8 run.py && flake8 run.py

EXPOSE 5005

CMD ["python3", "run.py", "-d"]
