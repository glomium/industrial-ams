#!/usr/bin/env python3

import grpc
import logging
import os

from google.protobuf.empty_pb2 import Empty

from iams.utils.grpc import framework_channel
from iams.utils.cfssl import CFSSL
from iams.stub import AgentStub

HOST = "10.6.30.69"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    ssl = CFSSL("127.0.0.1:8888", 2048)
    response = ssl.get_certificate(HOST, image="alpine", version="latest")
    certificate = response["result"]["certificate"]
    private_key = response["result"]["private_key"]

    credentials = HOST, grpc.ssl_channel_credentials(
        root_certificates=ssl.ca,
        private_key=private_key.encode(),
        certificate_chain=certificate.encode(),
    )

    print("connect to agent localhost")
    with framework_channel(credentials, proxy="localhost", port=5005) as channel:
        stub = AgentStub(channel)
        response = stub.ping(Empty())
        logger.info('got: %s', response)
    print("done")


if __name__ == '__main__':
    run()
