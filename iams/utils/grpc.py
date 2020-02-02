#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import time

from contextlib import contextmanager
from functools import wraps

import grpc

from ..proto.agent_pb2_grpc import add_AgentServicer_to_server


logger = logging.getLogger(__name__)


def get_credentials(node):
    if not node:
        node = os.environ.get('AMS_CORE', None)
        assert node is not None, 'Must define AMS_CORE in environment'

    # TODO read from filesystem
    pass
    # return node, grpc.ssl_channel_credentials(
    #     root_certificates=ca_public,
    #     private_key=private_key.encode(),
    #     certificate_chain=certificate.encode(),
    # )


class Grpc(object):
    def __init__(self, parent, servicer, threadpool, port):
        self.agent = servicer
        self.parent = parent
        self.server = grpc.server(threadpool)
        self.server.add_insecure_port(port)

        # directly add agent functionality to grpc interface
        add_AgentServicer_to_server(servicer, self.server)

    def add(self, function, servicer):
        function(servicer, self.server)

    def start(self):
        logger.debug("Starting grpc-server")
        self.server.start()

    def stop(self):
        self.server.stop(0)
        self.agent.stop()
        logger.debug("Stopped grpc-server")


@contextmanager
def framework_channel(credentials, proxy=None, port=443):
    server = proxy or credentials[0]
    options = [
        ('grpc.default_authority', credentials[0]),
        ('grpc.ssl_target_name_override', credentials[0]),
    ]

    with grpc.secure_channel(f'{server!s}:{port!s}', credentials[1], options=options) as channel:
        yield channel


def grpc_retry(f, transactional=False, internal=1, aborted=3, unavailable=10, deadline_exceeded=3, *args, **kwargs):
    retry_codes = {
        grpc.StatusCode.INTERNAL: os.environ.get("GRPC_RETRY_INTERNAL", internal),
        grpc.StatusCode.ABORTED: os.environ.get("GRPC_RETRY_ABORTED", aborted),
        grpc.StatusCode.UNAVAILABLE: os.environ.get("GRPC_RETRY_UNAVAILABLE", unavailable),
        grpc.StatusCode.DEADLINE_EXCEEDED: os.environ.get("GRPC_RETRY_DEADLINE_EXCEEDED", deadline_exceeded),
    }

    if isinstance(f, grpc.UnaryStreamMultiCallable):

        @wraps(f)
        def wrapper_stream(*args, **kwargs):
            retries = 0

            while True:
                try:
                    for x in f(*args, **kwargs):
                        yield x
                    break
                except grpc.RpcError as e:
                    code = e.code()
                    max_retries = retry_codes.get(code, 0)

                    retries += 1
                    if retries > max_retries or transactional and code == grpc.StatusCode.ABORTED:
                        raise

                    sleep = min(0.01 * retries ** 3, 1.0)
                    logger.debug("retrying failed request (%s) in %s seconds", code, sleep)
                    time.sleep(sleep)
        return wrapper_stream

    if isinstance(f, grpc.UnaryUnaryMultiCallable):
        @wraps(f)
        def wrapper_unary(*args, **kwargs):
            retries = 0

            while True:
                try:
                    return f(*args, **kwargs)
                except grpc.RpcError as e:
                    code = e.code()
                    max_retries = retry_codes.get(code, 0)

                    retries += 1
                    if retries > max_retries or transactional and code == grpc.StatusCode.ABORTED:
                        raise

                    sleep = min(0.01 * retries ** 3, 1.0)
                    logger.debug("retrying failed request (%s) in %s seconds", code, sleep)
                    time.sleep(sleep)
        return wrapper_unary
    return f