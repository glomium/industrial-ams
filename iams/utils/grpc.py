#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import time

from contextlib import contextmanager
from functools import wraps

import grpc

from ..constants import AGENT_CLOUDLESS
from ..constants import AGENT_PORT
from ..proto.agent_pb2_grpc import add_AgentServicer_to_server


logger = logging.getLogger(__name__)


def get_credentials():

    with open('/run/secrets/ca.crt', 'rb') as f:
        ca_public = f.read()
    with open('/run/secrets/peer.key', 'rb') as f:
        private_key = f.read()
    with open('/run/secrets/peer.crt', 'rb') as f:
        certificate = f.read()

    return ca_public, private_key, certificate


def get_channel_credentials():
    ca_public, private_key, certificate = get_credentials()

    return grpc.ssl_channel_credentials(
        root_certificates=ca_public,
        private_key=private_key,
        certificate_chain=certificate,
    )


def get_server_credentials():
    ca_public, private_key, certificate = get_credentials()

    return grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=ca_public,
        require_client_auth=True,
    )


class Grpc(object):
    def __init__(self, agent, threadpool, credentials):
        self.server = grpc.server(threadpool)
        if agent.cloud:
            self.server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)
        else:
            self.server.add_insecure_port(f'[::]:{AGENT_CLOUDLESS}')

        # directly add agent functionality to grpc interface
        add_AgentServicer_to_server(agent, self.server)

    def add(self, function, servicer):
        function(servicer, self.server)

    def start(self):
        logger.debug("Starting grpc-server")
        self.server.start()

    def stop(self):
        self.server.stop(0)
        logger.debug("Stopped grpc-server")


@contextmanager
def framework_channel(hostname=None, credentials=None, proxy=None, port=None, secure=True):
    server = proxy or hostname or os.environ.get("IAMS_SERVICE", None)
    port = port or AGENT_PORT

    if proxy is None:
        options = []
    else:
        options = [
            ('grpc.default_authority', hostname),
            ('grpc.ssl_target_name_override', hostname),
        ]

    logger.debug(f"connecting to %s:%s with options %s", server, port, options)

    if secure:
        with grpc.secure_channel(f'{server!s}:{port!s}', credentials, options=options) as channel:
            yield channel
    else:
        with grpc.insecure_channel(f'{server!s}:{port!s}', options=options) as channel:
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
