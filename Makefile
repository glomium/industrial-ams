VENV_NAME?=.venv
UBUNTU=rolling


build:
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --target basestage -t iams-base:local .
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --target test -t iams-test:local .
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --cache-from iams-build:local --cache-from iams:local -t iams:local .
	cd examples/simulation && docker build -f Dockerfile_carrier -t iams_simulation_carrier:local .
	cd examples/simulation && docker build -f Dockerfile_carrierpool -t iams_simulation_carrierpool:local .
	cd examples/simulation && docker build -f Dockerfile_machine1 -t iams_simulation_machine1:local .
	cd examples/simulation && docker build -f Dockerfile_machine2 -t iams_simulation_machine2:local .
	cd examples/simulation && docker build -f Dockerfile_order -t iams_simulation_order:local .
	cd examples/simulation && docker build -f Dockerfile_sink -t iams_simulation_sink:local .
	cd examples/simulation && docker build -f Dockerfile_source -t iams_simulation_source:local .
	cd examples/simulation && docker build -f Dockerfile_vehicle -t iams_simulation_vehicle:local .


buildx:
	docker buildx build --platform linux/amd64,linux/arm64 --build-arg UBUNTU=$(UBUNTU) -t glomium/industrial-ams:multiarch --push .


test: build
	docker stack deploy -c docker-test.yaml test
	docker service scale test_arangodb=1 test_sim=1 test_cfssl=1 test_coverage=1
	docker exec test_sim.1.`docker service ps test_sim -q --filter="desired-state=running"` /bin/bash run_tests.sh
	docker stack rm test


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
