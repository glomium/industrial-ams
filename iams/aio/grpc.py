#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

# from functools import partial
from contextlib import asynccontextmanager
import asyncio
import logging
# import os

import grpc

from iams.aio.interfaces import Coroutine

logger = logging.getLogger(__name__)


class GRPCCoroutine(Coroutine):
    """
    gRPC Coroutine
    """

    def __init__(self, credentials):
        self.credentials = credentials
        self.server = None

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self.server = grpc.aio.server()

    async def loop(self):
        """
        loop method contains the business-code
        """
        try:
            await self.server.wait_for_termination()
        except asyncio.CancelledError:
            # Shuts down the server with 0 seconds of grace period. During the
            # grace period, the server won't accept new connections and allow
            # existing RPCs to continue within the grace period.
            await self.server.stop(3)

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        await self.server.start()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        await self.server.stop(3)

    async def wait(self, setups):
        """
        stop method is called after the coroutine was canceled
        """
        await asyncio.wait(setups.values(), timeout=None)

    @asynccontextmanager
    async def channel(self, hostname=None):
        """
        channel context manager
        """
        server = hostname or "localhost"
        port = "1234"

        async with grpc.aio.secure_channel(f'{server!s}:{port!s}', self.credentials) as channel:
            return channel


class GRPCMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        credentials = None
        self._grpc = GRPCCoroutine(credentials)

    def _pre_setup(self):
        super()._pre_setup()
        self.task_manager.register(self._grpc)


_ = '''
from contextlib import ContextDecorator
from datetime import datetime
from datetime import timedelta
from functools import wraps
from pathlib import Path
import asyncio
import logging
import os

from cryptography import x509
from cryptography.hazmat.backends import default_backend
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
            self._certificate = x509.load_pem_x509_certificate(self.certificate, default_backend())

    def __call__(self, threadpool=None, port=None, insecure_port=None):
        if threadpool is None:
            self.server = grpc.aio.server()
        else:
            self.server = grpc.server(threadpool)

        if self.secure:
            port = AGENT_PORT if port is None else port
            self.port = self.server.add_secure_port(f'[::]:{port}', self.get_server_credentials())
            logger.debug("Open secure server on port %s", port)
        if insecure_port is not None:
            self.insecure_port = self.server.add_insecure_port(f'[::]:{insecure_port}')
            logger.debug("Open insecure server on port %s", insecure_port)

    def certificate_expire(self):
        """
        returns the time (in seconds) when the certificate expires
        """
        if self.secure:
            return self._certificate.not_valid_after - datetime.utcnow()
        return timedelta(7)

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
'''
