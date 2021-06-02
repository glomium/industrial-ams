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
from iams.constants import AGENT_PORT

logger = logging.getLogger(__name__)


class GRPCCoroutine(Coroutine):
    """
    gRPC Coroutine
    """

    def __init__(self, parent, credentials):
        self.credentials = credentials
        self.parent = parent
        self.server = None

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self.server = grpc.aio.server()
        self.server.add_insecure_port(f'[::]:{AGENT_PORT}')
        # self.server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)

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

        async with grpc.aio.secure_channel(f'{server!s}:{AGENT_PORT}', self.credentials) as channel:
            return channel


class GRPCMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        credentials = None
        self._grpc = GRPCCoroutine(self, credentials)

    def _pre_setup(self):
        super()._pre_setup()
        self.aio_manager.register(self._grpc)

    async def grpc_add(self, function, servicer):
        """
        add servicer
        """
        function(servicer, self._grpc.server)

    async def grpc_start(self):
        """
        callback when grpc started
        """
