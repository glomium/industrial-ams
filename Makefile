VENV_NAME?=.venv
UBUNTU=rolling

build:
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --target basestage -t iams-base:local .
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --target test -t iams-test:local .
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --cache-from iams-build:local --cache-from iams:local -t iams:local .
	cd examples/simulation && docker build -f Dockerfile_source -t iams_simulation_source:local .
	cd examples/simulation && docker build -f Dockerfile_sink -t iams_simulation_sink:local .
	cd examples/simulation && docker build -f Dockerfile_vehicle -t iams_simulation_vehicle:local .
	cd examples/market && docker build -f Dockerfile_source -t iams_market_source:local .
	cd examples/market && docker build -f Dockerfile_sink -t iams_market_sink:local .

test: start
	curl --request DELETE 127.0.0.1:8000
	pip install .
	iams-simulation examples/simulation/simulation.yaml 127.0.0.1:5115
	sleep 10
	curl 127.0.0.1:8000 --output .coverage
# 	iams-simulation examples/market/simulation.yaml 127.0.0.1:5115

certs:
	mkdir -p secrets
	openssl genrsa -out secrets/ca.key 8192
	openssl req -x509 -new -SHA384 -key secrets/ca.key -out secrets/ca.crt -days 36525

start:
	docker stack deploy -c docker-compose.yaml iams 
	docker service update --force iams_ctrl -d
	docker service update --force iams_sim

stop:
	docker stack rm iams 

pip:
	${VENV_NAME}/bin/pip-upgrade requirements/dev.txt requirements/docs.txt requirements/test.txt --skip-package-installation
