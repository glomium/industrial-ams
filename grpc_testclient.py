#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import grpc
import logging

from google.protobuf.empty_pb2 import Empty

from iams.utils.grpc import framework_channel
from iams.utils.cfssl import CFSSL
from iams.stub import FrameworkStub

HOST = "192.168.42.65"
HOST = "10.6.30.69"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def run():
    ssl = CFSSL("127.0.0.1:8888", 2048, [HOST])
    response = ssl.get_certificate(HOST, groups=["root", "web"])
    certificate = response["result"]["certificate"]
    private_key = response["result"]["private_key"]

    credentials = "tasks.sim", grpc.ssl_channel_credentials(
        root_certificates=ssl.ca,
        private_key=private_key.encode(),
        certificate_chain=certificate.encode(),
    )

    for port, secure in [(None, True)]:
        logger.info("connect to agent on %s:%s", HOST, port)
        # with framework_channel(credentials, host="localhost" port=5005) as channel:
        with framework_channel(credentials, proxy=HOST, port=port, secure=secure) as channel:
            stub = FrameworkStub(channel)
            response = stub.booted(Empty())
        logger.info('got: %s', response)


if __name__ == '__main__':
    run()
