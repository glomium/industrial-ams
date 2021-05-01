#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grpc helper
"""

from contextlib import ContextDecorator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import logging
import os

import grpc

from iams.constants import AGENT_PORT


logger = logging.getLogger(__name__)


class Grpc(ContextDecorator):  # pylint: disable=too-many-instance-attributes
    """
    grpc container class
    """

    __hash__ = None

    def __init__(self, name, ca=None, secure=True, secret_folder=Path("/run/secrets/")):

        self._certificate = None
        self._credentials = None
        self._secret_folder = secret_folder
        self.certificate = None
        self.insecure_port = None
        self.port = None
        self.secure = (secure is True)
        self.server = None

        if ca is None:
            if secure:
                self._credentials = self.credentials_from_secrets()
        elif secure:  # pragma: no branch
            ca_public = ca.get_root_cert()
            self.certificate, private_key = ca.get_agent_certificate(name)
            self._credentials = ca_public, private_key

    def __call__(self, threadpool, port=None, insecure_port=None):
        self.server = grpc.server(threadpool)
        if self.secure:
            port = AGENT_PORT if port is None else port
            self.port = self.server.add_secure_port(f'[::]:{port}', self.get_server_credentials())
            logger.debug("Open secure server on port %s", port)
        if insecure_port is not None:
            self.insecure_port = self.server.add_insecure_port(f'[::]:{insecure_port}')
            logger.debug("Open insecure server on port %s", insecure_port)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.stop()

    def credentials_from_secrets(self):
        """
        read credentials from secrets
        """
        with open(self._secret_folder / 'ca.crt', 'rb') as fobj:
            ca_public = fobj.read()
        with open(self._secret_folder / 'peer.key', 'rb') as fobj:
            private_key = fobj.read()
        with open(self._secret_folder / 'peer.crt', 'rb') as fobj:
            self.certificate = fobj.read()
        return ca_public, private_key

    def get_channel_credentials(self):
        """
        get channel certificate
        """
        ca_public, private_key = self._credentials

        return grpc.ssl_channel_credentials(
            root_certificates=ca_public,
            private_key=private_key,
            certificate_chain=self.certificate,
        )

    def get_server_credentials(self):
        """
        get server certificate
        """
        ca_public, private_key = self._credentials

        return grpc.ssl_server_credentials(
            ((private_key, self.certificate),),
            root_certificates=ca_public,
            require_client_auth=True,
        )

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
    def channel(self, hostname=None, proxy=None, port=None, secure=True):
        """
        channel context manager
        """
        if secure:
            channel_credentials = self.get_channel_credentials()
        else:
            channel_credentials = None
        with framework_channel(hostname, channel_credentials, proxy, port, secure) as channel:
            yield channel


@contextmanager
def framework_channel(hostname=None, channel_credentials=None, proxy=None, port=None, secure=True):
    """
    framework channel context manager
    """
    server = proxy or hostname or os.environ.get("IAMS_SERVICE", None)
    port = port or AGENT_PORT

    if server is None:
        raise ValueError("No Endpoint specified")

    if proxy is None:
        options = []
    else:
        options = [
            ('grpc.default_authority', hostname),
            ('grpc.ssl_target_name_override', hostname),
        ]

    logger.debug("connecting to %s:%s with options %s", server, port, options)
    if secure:
        with grpc.secure_channel(
            f'{server!s}:{port!s}',
            channel_credentials,
            options=options,
        ) as channel:
            yield channel
    else:
        with grpc.insecure_channel(
            f'{server!s}:{port!s}',
            options=options,
        ) as channel:
            yield channel


def credentials(function=None, optional=False):
    """
    credentials decorator (adds a "credentials" attribute to the grpc-context)
    """

    def decorator(func):
        @wraps(func)
        def wrapped(self, request, context=None):

            # internal request
            if hasattr(context, "credentials") and isinstance(context.credentials, set):
                logger.debug("Process request as it already as a credentials attribute (internal request)")
                return func(self, request, context)

            # assign peer identities
            try:
                context.credentials = set(
                    x.decode('utf-8') for x in context.peer_identities() if x not in [b'127.0.0.1', b'localhost']
                )
            except TypeError:
                logger.debug("Could not assign the 'credentials' attribute")
                if optional:
                    context.credentials = set()
                    return func(self, request, context)
            else:
                return func(self, request, context)

            # abort unauthentifcated call
            message = "Client needs to be authentifacted"
            logger.debug(message)
            return context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return wrapped

    if function:
        return decorator(function)
    return decorator
