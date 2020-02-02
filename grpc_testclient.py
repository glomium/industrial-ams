#!/usr/bin/env python3

import grpc
import logging
import os

from google.protobuf.empty_pb2 import Empty

from iams.utils.grpc import framework_channel
from iams.utils.cfssl import get_ca_public_key
from iams.utils.cfssl import get_certificate
from iams.stub import FrameworkStub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
os.environ.setdefault('IAMS_CFSSL', '127.0.0.1:8888')


def run():
    print("get certificates")
    ca_public = get_ca_public_key()
    response = get_certificate('localhost', image="alpine", version="latest")
    certificate = response["result"]["certificate"]
    private_key = response["result"]["private_key"]

    credentials = "localhost", grpc.ssl_channel_credentials(
        root_certificates=ca_public,
        private_key=private_key.encode(),
        certificate_chain=certificate.encode(),
    )

    print("connect to agent localhost")
    with framework_channel(credentials, proxy="localhost", port=9999) as channel:
        stub = FrameworkStub(channel)
        for response in stub.agents(Empty()):
            logger.info('got: %s', response)


if __name__ == '__main__':
    run()
