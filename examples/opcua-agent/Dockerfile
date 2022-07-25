FROM iams-test:local

LABEL iams.services.agent=true
LABEL iams.plugins.influxdb=MySensor

RUN pip install asyncua==0.9.94 influxdb==5.3.1

COPY run.py ./run.py

ENTRYPOINT ["/usr/bin/python3", "run.py"]
