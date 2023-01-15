.PHONY: static
static:
	flake8 iams
	doc8 iams
	pylint iams


.PHONY: grpc
grpc:
	python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto \
		proto/agent.proto \
		proto/ca.proto \
		proto/df.proto \
		proto/framework.proto
	sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py


.PHONY: wheel
wheel: grpc
	pip wheel --no-deps -w dist .


# not used in github actions
.PHONY: build
build: wheel
	docker build --cache-from iams-base:local --pull --target basestage -t iams-base:local .
	docker build --cache-from iams-base:local --cache-from iams-test:local --target test -t iams-test:local .
	docker build --cache-from iams-base:local --cache-from iams-test:local --cache-from iams-build:local --cache-from iams:local -t iams:local .


# not used in github actions
buildx:
	docker buildx build --pull --platform linux/amd64,linux/arm64 -t glomium/industrial-ams:$(TARGET) --push .


# not used in github actions
.PHONY: test
test: static
	coverage run -m unittest -v
	coverage report


# not used in github actions
run_test_services:
	docker-compose -f docker-test.yaml up --abort-on-container-exit


# not used in github actions
test2: build
	docker stack deploy -c docker-test.yaml test
	docker service scale test_arangodb=1 test_sim=1 test_cfssl=1 test_coverage=1
	docker exec test_sim.1.`docker service ps test_sim -q --filter="desired-state=running"` /bin/bash run_tests.sh
	docker stack rm test


# not used in github actions
certs:
	mkdir -p secrets
	# openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -x509 -nodes -days 36525 -out secrets/ec_ca.crt -keyout secrets/ec_ca.key
	openssl genrsa -out secrets/ca.key 8192
	openssl req -x509 -new -SHA384 -key secrets/ca.key -out secrets/ca.crt -days 36525


# not used in github actions
start: build
	docker stack deploy -c docker-compose.yaml iams 
	docker service update --force iams_ctrl -d
	docker service update --force iams_sim


# not used in github actions
stop:
	docker stack rm iams 


# not used in github actions
pip:
	.venv/bin/pip-upgrade requirements.txt requirements/build.txt requirements/dev.txt requirements/docs.txt requirements/test.txt --skip-package-installation
