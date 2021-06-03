#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import logging

import grpc

from iams.aio.interfaces import Coroutine
from iams.constants import AGENT_PORT

logger = logging.getLogger(__name__)


class GRPCCoroutine(Coroutine):
    """
    gRPC Coroutine
    """

    def __init__(self, parent, secret_folder=Path("/run/secrets/")):
        self.parent = parent
        self.server = None
        try:
            with open(secret_folder / 'ca.crt', 'rb') as fobj:
                root_certificate = fobj.read()
            with open(secret_folder / 'peer.key', 'rb') as fobj:
                private_key = fobj.read()
            with open(secret_folder / 'peer.crt', 'rb') as fobj:
                certificate_chain = fobj.read()
        except FileNotFoundError:
            self.credentials = None
        else:
            self.credentials = grpc.ssl_channel_credentials(
                root_certificates=root_certificate,
                private_key=private_key,
                certificate_chain=certificate_chain,
            )

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self.server = grpc.aio.server()
        if self.credentials is None:
            logger.warning("No credentials found - using insecure port")
            self.server.add_insecure_port(f'[::]:{AGENT_PORT}')
        else:
            self.server.add_secure_port(f'[::]:{AGENT_PORT}', self.credentials)

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
            await self.server.stop(2)

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        await self.server.start()
        await self.parent.grpc_start()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        await self.server.stop(3)

    async def wait(self, tasks):
        """
        stop method is called after the coroutine was canceled
        """
        await asyncio.wait(tasks.values(), timeout=None)

    @asynccontextmanager
    async def channel(self, hostname=None):
        """
        channel context manager
        """
        server = hostname or "localhost"

        async with grpc.aio.secure_channel(f'{server!s}:{AGENT_PORT}', self.credentials) as channel:
            return channel


class GRPCMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._grpc = GRPCCoroutine(self)

    def _setup(self):
        self.aio_manager.register(self._grpc)
        super()._setup()

    def grpc_add(self, function, servicer):
        """
        add servicer
        """
        function(servicer, self._grpc.server)

    async def grpc_start(self):
        """
        callback when grpc started
        """
