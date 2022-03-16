#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add GRPC functionality to agents
"""

from abc import ABC
from abc import abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import AsyncIterator
import asyncio
import logging

from google.protobuf.empty_pb2 import Empty
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
        try:
            await self.server.wait_for_termination()
        except asyncio.CancelledError:
            pass

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
        try:
            await self.server.stop(1.0)
        except asyncio.CancelledError:
            pass

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


class GRPCConnectionCoroutine(ABC):  # pylint: disable=too-many-instance-attributes
    """
    gRPC connection coroutine
    """
    GRPC_METHOD = "status"

    def __init__(self, agent, parent, name):
        super().__init__()
        logger.debug("Init: GRPC connection to %s", name)

        self.agent = agent
        self.connected = False
        self.data = None
        self.hostname = agent.iams.prefix + name
        self.name = name
        self.parent = parent
        self.previous = self.grpc_default()
        self.task = None

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__qualname__}({self.name})>"

    async def __call__(self):
        """
        starts the coroutine
        """
        if self.task is None or self.task.done():
            logger.debug("Start: GRPC connection to %s", self.name)
            self.task = asyncio.create_task(self._main(), name=f"GRPCConnection.{self.name}")

    async def stop(self):
        """
        closes the connection and stops the coroutine
        """
        if self.task is not None and not self.task.done():
            self.task.cancel()

    @staticmethod
    def grpc_default():
        """
        returns the default grpc value for the status message
        """
        return None

    def grpc_method(self):
        """
        returns the default grpc method
        """
        return self.GRPC_METHOD

    @staticmethod
    def grpc_options():
        """
        returns the grpc options for the persistent connection
        """
        return {
            # This channel argument controls the period (in milliseconds) after which a keepalive
            # ping is sent on the transport.
            'grpc.keepalive_time_ms': 10000,
            # This channel argument controls the amount of time (in milliseconds) the sender of
            # the keepalive ping waits for an acknowledgement. If it does not receive an acknowledgment
            # within this time, it will close the connection.
            'grpc.keepalive_timeout_ms': 5000,
            # This channel argument if set to 1 (0 : false; 1 : true), allows
            # keepalive pings to be sent even if there are no calls in flight.
            'grpc.keepalive_permit_without_calls': 1,
            # This channel argument controls the maximum number of pings that can be sent when
            # there is no data/header frame to be sent. gRPC Core will not continue sending pings if
            # we run over the limit. Setting it to 0 allows sending pings without such a restriction.
            'grpc.http2.max_pings_without_data': 0,
        }

    @abstractmethod
    def grpc_stub(self):
        """
        returns the default grpc stub
        """

    @staticmethod
    def grpc_payload():
        """
        returns the default grpc payload
        """
        return Empty()

    @abstractmethod
    async def process(self, response):
        """
        process new data
        """

    async def connect(self):
        """
        connect callback
        """

    async def disconnect(self):
        """
        disconnect callback
        """

    async def _main(self):
        """
        manages the connection
        """
        wait = 0
        kwargs = {
            'hostname': self.hostname,
            'persistent': False,
            'options': self.grpc_options(),
        }

        try:
            while True:
                try:
                    async with self.agent.grpc.stub(self.grpc_stub(), **kwargs) as stub:  # noqa: E501
                        method = getattr(stub, self.grpc_method())
                        payload = self.grpc_payload()
                        async for response in method(payload):
                            if self.connected:
                                self.previous = self.data
                                self.data = response
                            else:
                                wait = 0
                                self.connected = True
                                logger.info(
                                    "Connection to %s etablished",
                                    self.hostname,
                                )
                                self.previous = self.grpc_default()
                                self.data = response
                                await self.connect()
                            await self.process(response)
                except grpc.RpcError as error:
                    if self.connected:
                        logger.info(
                            "Disconnected (%s) from %s: %s",
                            error.code(),  # pylint: disable=no-member
                            self.hostname,
                            error.details(),  # pylint: disable=no-member
                        )
                        self.connected = False
                        await self.disconnect()
                    else:
                        logger.debug(
                            "Connection rejected (%s) by %s: %s",
                            error.code(),  # pylint: disable=no-member
                            self.hostname,
                            error.details(),  # pylint: disable=no-member
                        )
                    wait = min(15, wait + 0.3)
                    await asyncio.sleep(wait)

        except asyncio.CancelledError:
            pass

        except Exception:
            logger.exception('Error in %s._main', self.__class__.__qualname__)
            raise
