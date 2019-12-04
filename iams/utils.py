#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import time

from contextlib import contextmanager
from functools import wraps

import grpc

from .proto.agent_pb2_grpc import add_AgentServicer_to_server


logger = logging.getLogger(__name__)


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


class ClientInterceptor(
        grpc.UnaryUnaryClientInterceptor, grpc.UnaryStreamClientInterceptor,
        grpc.StreamUnaryClientInterceptor, grpc.StreamStreamClientInterceptor):

    def intercept(self, continuation, client, request):

        if client.metadata:
            metadata = list(client.metadata)
        else:
            metadata = []

        for k, e in (
            ("x-ams-agent", 'AMS_AGENT'),
            ("x-ams-image", 'AMS_IMAGE'),
            ("x-ams-version", 'AMS_VERSION'),
        ):
            value = os.environ.get(e)
            if value:
                metadata.append((k, value))

        calldetails = grpc.ClientCallDetails()
        calldetails.method = client.method
        calldetails.timeout = client.timeout
        calldetails.metadata = metadata
        calldetails.credentials = client.credentials

        return continuation(calldetails, request)

    def intercept_unary_unary(self, continuation, client, request):
        return self.intercept(continuation, client, request)

    def intercept_unary_stream(self, continuation, client, request):
        return self.intercept(continuation, client, request)

    def intercept_stream_unary(self, continuation, client, request_iterator):
        return self.intercept(continuation, client, request_iterator)

    def intercept_stream_stream(self, continuation, client, request_iterator):
        return self.intercept(continuation, client, request_iterator)


def agent_required(f):
    @wraps(f)
    def wrapper(self, request, context):
        metadata = dict(context.invocation_metadata())
        try:
            assert "x-ams-agent" in metadata, "'x-ams-agent' missing in metadata"
            assert "x-ams-image" in metadata, "'x-ams-image' missing in metadata"
            assert "x-ams-version" in metadata, "'x-ams-version' missing in metadata"
        except AssertionError as e:
            message = 'Permission denied: %s' % e
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        context._agent = metadata['x-ams-agent']
        context._image = metadata['x-ams-image']
        context._version = metadata['x-ams-version']
        return f(self, request, context)
    return wrapper


@contextmanager
def framework_channel(node=None, proxy=None, port=80):

    if not node:
        node = os.environ.get('AMS_CORE', None)
        assert node is not None, 'Must define AMS_CORE in environment'
    server = proxy or node

    options = [
        ('grpc.default_authority', node),
        ('grpc.ssl_target_name_override', node),
    ]

    with grpc.insecure_channel(f'{server!s}:{port!s}', options=options) as channel:
        channel = grpc.intercept_channel(channel, ClientInterceptor())
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
