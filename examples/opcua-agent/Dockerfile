FROM ubuntu:latest

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONUNBUFFERED=1

LABEL iams.services.agent=true
LABEL iams.plugins.influxdb=MySensor

RUN apt-get update && apt-get install --no-install-recommends -y -q \
    python3 \
    python3-pip \
&& pip install iams asyncua influxdb \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

COPY run.py ./run.py

ENTRYPOINT ["/usr/bin/python3", "run.py"]
