VENV_NAME?=.venv
UBUNTU=rolling

build: test
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --cache-from iams-build:local --cache-from iams:local -t iams:local .

test:
	docker pull $(REGISTRY)/iams:$(UBUNTU) || true
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --target basestage -t iams-base:local .
	docker build --build-arg UBUNTU=$(UBUNTU) --cache-from iams-base:local --cache-from iams-test:local --target test -t iams-test:local .

certs:
	mkdir -p secrets
	openssl genrsa -out secrets/ca.key 8192
	openssl req -x509 -new -SHA384 -key secrets/ca.key -out secrets/ca.crt -days 36525

start: build
	docker stack deploy -c docker-compose.yaml iams 
	docker service update --force iams_ctrl -d
	docker service update --force iams_sim -d

grpc:
	mkdir -p iams/proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/framework.proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/simulation.proto
	sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iexamples/agv --python_out=examples/agv --grpc_python_out=examples/agv examples/agv/agv.proto

pip:
	${VENV_NAME}/bin/pip-upgrade requirements-dev.txt requirements-test.txt --skip-package-installation
