#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grpc helper
"""

import logging
import os

from contextlib import contextmanager

import grpc

from iams.constants import AGENT_PORT
from iams.proto.agent_pb2_grpc import add_AgentServicer_to_server


logger = logging.getLogger(__name__)


def get_credentials():
    """
    read credentials from secrets
    """

    with open('/run/secrets/ca.crt', 'rb') as fobj:
        ca_public = fobj.read()
    with open('/run/secrets/peer.key', 'rb') as fobj:
        private_key = fobj.read()
    with open('/run/secrets/peer.crt', 'rb') as fobj:
        certificate = fobj.read()

    return ca_public, private_key, certificate


def get_channel_credentials():
    """
    get channel certificate
    """
    ca_public, private_key, certificate = get_credentials()

    return grpc.ssl_channel_credentials(
        root_certificates=ca_public,
        private_key=private_key,
        certificate_chain=certificate,
    )


def get_server_credentials():
    """
    get server certificate
    """
    ca_public, private_key, certificate = get_credentials()

    return grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=ca_public,
        require_client_auth=True,
    )


class Grpc:
    """
    grpc container class
    """

    __hash__ = None

    def __init__(self, agent, threadpool, credentials):
        self.server = grpc.server(threadpool)
        self.server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)

        # directly add agent functionality to grpc interface
        add_AgentServicer_to_server(agent, self.server)

    def add(self, function, servicer):
        """
        add servicer
        """
        function(servicer, self.server)

    def start(self):
        """
        start server
        """
        logger.debug("Starting grpc-server")
        self.server.start()

    def stop(self):
        """
        stop server
        """
        self.server.stop(None)
        logger.debug("Stopped grpc-server")


@contextmanager
def framework_channel(hostname=None, credentials=None, proxy=None, port=None, secure=True):
    """
    framework channel context manager
    """
    server = proxy or hostname or os.environ.get("IAMS_SERVICE", None)
    port = port or AGENT_PORT

    if proxy is None:
        options = []
    else:
        options = [
            ('grpc.default_authority', hostname),
            ('grpc.ssl_target_name_override', hostname),
        ]

    logger.debug("connecting to %s:%s with options %s", server, port, options)

    if secure:
        with grpc.secure_channel(f'{server!s}:{port!s}', credentials, options=options) as channel:
            yield channel
    else:
        with grpc.insecure_channel(f'{server!s}:{port!s}', options=options) as channel:
            yield channel
