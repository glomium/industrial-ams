FROM glomium/industrial-ams:rolling

LABEL iams.services.agent=true

COPY run.py ./run.py

ENTRYPOINT ["/usr/bin/python3", "run.py"]
