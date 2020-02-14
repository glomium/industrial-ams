VENV_NAME?=.venv
ALPINE=3.11.3
REGISTRY=registry:5000

build: test
	docker build --build-arg ALPINE=$(ALPINE) --cache-from iams-base:latest --cache-from iams-test:latest --cache-from iams-build:latest --cache-from $(REGISTRY)/iams:$(ALPINE) -t $(REGISTRY)/iams:latest -t $(REGISTRY)/iams:$(ALPINE) .
	docker push $(REGISTRY)/iams:$(ALPINE)
	docker push $(REGISTRY)/iams:latest

test:
	docker pull $(REGISTRY)/iams:$(ALPINE) || true
	docker build --build-arg ALPINE=$(ALPINE) --cache-from iams-base:latest --target basestage -t iams-base:latest .
	docker build --build-arg ALPINE=$(ALPINE) --cache-from iams-base:latest --cache-from iams-test:latest --target test -t iams-test:latest .

grpc:
	mkdir -p iams/proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/agent.proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/framework.proto
	${VENV_NAME}/bin/python3 -m grpc_tools.protoc -Iproto --python_out=iams/proto --grpc_python_out=iams/proto proto/simulation.proto
	sed -i -E 's/^import.*_pb2/from . \0/' iams/proto/*.py

pip:
	${VENV_NAME}/bin/pip-upgrade requirements.txt requirements-dev.txt requirements-test.txt --skip-package-installation
