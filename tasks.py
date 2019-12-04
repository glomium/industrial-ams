#!/usr/bin/python
# ex:set fileencoding=utf-8:

import os

from invoke import task

DIR = os.path.dirname(__file__)
PYTHON = ".venv/bin/python3"
GRPC_PROTO_FILES = {
    "proto/agent.proto": "iams/proto",
    "proto/framework.proto": "iams/proto",
    "proto/simulation.proto": "iams/proto",
}


@task(default=True)
def default(c):
    proto(c)


@task()
def proto(c):
    with c.cd(DIR):
        for f, d in GRPC_PROTO_FILES.items():
            c.run(f"mkdir -p {d}")
            source = os.path.dirname(f)
            c.run(f"{PYTHON} -m grpc_tools.protoc -I{source} --python_out={d} --grpc_python_out={d} {f}")
            c.run(f"sed -i -E 's/^import.*_pb2/from . \\0/' {d}/*.py")


@task()
def pip_upgrade(c):
    with c.cd(DIR):
        c.run('.venv/bin/pip-upgrade %s --skip-package-installation' % ' '.join([
            'requirements.txt',
            'requirements-dev.txt',
            'requirements-test.txt',
        ]))
