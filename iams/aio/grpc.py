#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import AsyncIterator
import asyncio
import logging

import grpc

from iams.aio.interfaces import Coroutine
from iams.constants import AGENT_PORT

logger = logging.getLogger(__name__)


@dataclass
class Channel:  # pylint: disable=too-many-instance-attributes
    """
    Manges gRPC channels
    """
    key: str
    persistent: bool = field(compare=False)
    options: dict = field(default_factory=dict, init=False, compare=False)
    stubs: dict = field(default_factory=dict, init=False, compare=False, repr=False)
    instance: object = field(default=None, repr=False, init=False, compare=False)
    connections: int = field(default=0, repr=False, init=False, compare=False)

    def __hash__(self):
        return hash(self.key)


class GRPCCoroutine(Coroutine):  # pylint: disable=too-many-instance-attributes
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
        self.channels = {}

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
        self.server = grpc.aio.server(
            interceptors=self.parent.grpc_interceptors(),
            options=tuple((self.parent.grpc_options() or {}).items()),
        )
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
        await self.server.wait_for_termination()

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
        logger.info("Gracefully stopping gRPC server")
        # Shuts down the server with 1.0 seconds of grace period. During the
        # grace period, the server won't accept new connections and allow
        # existing RPCs to continue within the grace period.
        # After the grace period all connections are closed
        await self.server.stop(1.0)

    async def wait(self, tasks):
        """
        wait for all tasks to finish
        """
        await super().wait(tasks)
        await asyncio.wait(tasks.values(), timeout=None)

    async def _channel(self, hostname, port, persistent, options):
        """
        get channel
        """
        server = hostname or self.manager
        key = f"{server!s}:{port!s}"
        try:
            channel = self.channels[key]
        except KeyError:
            self.channels[key] = Channel(
                key=key,
                persistent=persistent,
            )
            channel = self.channels[key]

        recreate = False
        if persistent and not channel.persistent:
            channel.peristent = True
            recreate = True

        if isinstance(options, dict):
            for key, value in options.items():
                if channel.options.get(key, None) != value:
                    channel.options[key] = value
                    recreate = True

        if recreate and channel.instance:
            await channel.instance.close()
            channel.instance = None

        if channel.instance is None:
            logger.debug("Create grpc-channel to %s with %s", channel.key, channel.options)
            if self.channel_credentials is None:
                channel.instance = grpc.aio.insecure_channel(
                    channel.key,
                    options=tuple(channel.options.items()),
                )
            else:
                channel.instance = grpc.aio.secure_channel(
                    channel.key,
                    self.channel_credentials,
                    options=tuple(channel.options.items()),
                )

        return channel

    @staticmethod
    async def get_stub(channel, stub):
        """
        get stub
        """
        try:
            return channel.stubs[stub.__qualname__]
        except KeyError:
            channel.stubs[stub.__qualname__] = stub(channel.instance)

        return channel.stubs[stub.__qualname__]

    @asynccontextmanager
    async def stub(self, stub, hostname=None, port=AGENT_PORT, persistent=False, options=None) -> AsyncIterator:  # noqa: E501  # pylint: disable=too-many-arguments
        """
        channel context manager
        """
        async with self.channel(hostname=hostname, port=port, persistent=persistent, options=options) as channel:
            try:
                yield channel.stubs[stub.__qualname__]
            except KeyError:
                channel.stubs[stub.__qualname__] = stub(channel.instance)
                yield channel.stubs[stub.__qualname__]

    @asynccontextmanager
    async def channel(self, hostname=None, port=AGENT_PORT, persistent=True, options=None) -> AsyncIterator:
        """
        channel context manager
        """
        channel = await self._channel(hostname, port, persistent, options)
        channel.connections += 1
        yield channel
        channel.connections -= 1
        if not channel.persistent and channel.connections <= 0:
            del self.channels[channel.key]
            await channel.instance.close()


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

    def grpc_interceptors(self):
        """
        callback when grpc started
        """

    def grpc_options(self):
        """
        callback when grpc started
        """

    async def grpc_start(self):
        """
        callback when grpc started
        """
