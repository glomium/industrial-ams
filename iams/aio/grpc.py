#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
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

    def __init__(  # pylint: disable=too-many-arguments
            self, parent,
            root_certificate=None, private_key=None, certificate_chain=None,
            secret_folder=Path("/run/secrets/"),
            port=AGENT_PORT,
    ):
        logger.debug("Initialize gRPC coroutine")
        self.manager = "localhost"
        self.parent = parent
        self.port = port
        self.server = None
        self.servicer = []
        try:
            if root_certificate is None:
                with open(secret_folder / 'ca.crt', 'rb') as fobj:
                    root_certificate = fobj.read()
            if private_key is None:
                with open(secret_folder / 'peer.key', 'rb') as fobj:
                    private_key = fobj.read()
            if certificate_chain is None:
                with open(secret_folder / 'peer.crt', 'rb') as fobj:
                    certificate_chain = fobj.read()
        except (FileNotFoundError, TypeError):
            self.channel_credentials = None
            self.server_credentials = None
        else:
            self.channel_credentials = grpc.ssl_channel_credentials(
                root_certificates=root_certificate,
                private_key=private_key,
                certificate_chain=certificate_chain,
            )
            self.server_credentials = grpc.ssl_server_credentials(
                ((private_key, certificate_chain),),
                root_certificates=root_certificate,
                require_client_auth=True,
            )

    def add(self, function, servicer):
        """
        add servicer to server
        """
        if self.server is None:
            self.servicer.append((function, servicer))
        else:
            function(servicer, self.server)

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self.server = grpc.aio.server()
        for function, servicer in self.servicer:
            function(servicer, self.server)
        self.servicer = []

        port = AGENT_PORT if self.port is None else self.port
        if self.server_credentials is None:
            logger.warning("No credentials found - using insecure port")
            self.port = self.server.add_insecure_port(f'[::]:{port}')
        else:
            self.port = self.server.add_secure_port(f'[::]:{port}', self.server_credentials)

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
        logger.info("gRPC server initialized")
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
    async def channel(self, hostname=None, port=AGENT_PORT) -> AsyncIterator:
        """
        channel context manager
        """
        server = hostname or self.manager
        if self.channel_credentials is None:
            async with grpc.aio.insecure_channel(f'{server!s}:{port!s}') as channel:
                yield channel
        else:
            async with grpc.aio.secure_channel(f'{server!s}:{port!s}', self.channel_credentials) as channel:
                yield channel


class GRPCMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grpc = GRPCCoroutine(self)

    def _setup(self):
        self.aio_manager.register(self.grpc)
        super()._setup()

    async def grpc_start(self):
        """
        callback when grpc started
        """
