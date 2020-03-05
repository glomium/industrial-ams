# The image requires to run the build of iams on your setup
# Change FROM to the public image to build from dockerhub
# FROM glomium/industrial-ams:rolling
FROM iams:local

LABEL iams.services.agent=true

COPY run.py ./run.py

ENTRYPOINT ["/usr/bin/python3", "run.py"]
