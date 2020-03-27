#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import logging

from logging.config import dictConfig

import grpc

from google.protobuf.empty_pb2 import Empty

from .helper import get_logging_config
from .stub import SimulationStub
from .utils.grpc import framework_channel


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'host',
        help="gRPC interfaces for simulation runtimes",
        default="127.0.0.1:80",
        nargs="?",
    )
    args = parser.parse_args()
    dictConfig(get_logging_config(["iams"], logging.INFO))
    logger = logging.getLogger(__name__)

    server, port = args.host.split(':')
    port = int(port)
    logger.info("connect to runtime at %s:%s", server, port)

    try:
        with framework_channel(server, port=port, secure=False) as channel:
            stub = SimulationStub(channel)
            stub.shutdown(Empty())

    except grpc.RpcError as e:  # pragma: no cover
        if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            logger.debug("got error message: %s", e.details())
            logger.info("simulation running on %s - try next runtime", server)
        else:
            raise
