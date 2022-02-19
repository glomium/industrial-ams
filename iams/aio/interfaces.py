#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams coroutine interfaces
"""

from abc import ABC
from abc import abstractmethod
import asyncio
import logging

import grpc


logger = logging.getLogger(__name__)


class Coroutine(ABC):
    """
    Coroutine Abstract Base Class
    """

    __hash__ = None

    async def __call__(self, setups):
        logger.debug("Starting %s", self)
        await self.wait(setups)
        try:
            await self.loop()
        except asyncio.CancelledError:
            await self.stop()
        logger.debug("%s stopped", self)

    def __repr__(self):
        return f"{self.__class__.__qualname__}()"

    def __str__(self):
        return self.__class__.__qualname__

    async def setup(self, executor):
        """
        setup method is awaited once at the start of the coroutines
        """

    async def _start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        await self.start()

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """

    async def wait(self, tasks):
        """
        The wait method can be used to delay the startup of a coroutine until preconditions are fulfilled
        """
        await asyncio.wait_for(tasks[str(self)], timeout=None)

    @abstractmethod
    async def loop(self):
        """
        loop method contains the business-code
        """

    @abstractmethod
    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """


class ThreadCoroutine(Coroutine):
    """
    Coroutine Abstract Base Class for threads
    """

    def __init__(self):
        self._executor = None
        self._stop = None

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self._executor = executor
        self._stop = asyncio.get_running_loop().create_future()

    async def loop(self):
        """
        loop method contains the business-code
        """
        await asyncio.wait_for(self._stop, timeout=None)

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if not self._stop.done():
            self._stop.set_result(None)
            return True
        return False


class EventCoroutine(Coroutine, ABC):
    """
    Coroutine Abstract Base Class for threads
    """
    INTERVAL = None

    def __init__(self):
        self._event = None
        self._executor = None
        self._stop = None
        self._lock = None

    async def _start(self):
        """
        setup method is awaited one at the start of the coroutines
        """
        await super()._start()
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._stop = asyncio.get_running_loop().create_future()

    def get_interval(self):
        """
        returns the interval of this events
        if None (the default), this function waits for the next event (i.e. call of self.run)
        """
        return self.INTERVAL

    @abstractmethod
    async def main(self, periodic):
        """
        stop method is called after the coroutine was canceled
        """

    async def loop(self):
        """
        loop method contains the business-code
        """
        while not self._stop.done():
            try:
                await asyncio.wait_for(self._event.wait(), timeout=self.get_interval())
            except asyncio.TimeoutError:
                periodic = True
            except asyncio.CancelledError:
                break
            else:
                periodic = False
            async with self._lock:
                await self.main(periodic=periodic)
        await self.stop()

    async def run(self):
        """
        redirects loop to a seperate task
        """
        self._event.set()
        self._event.clear()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if self._stop is not None and not self._stop.done():
            self._stop.set_result(True)
        if self._event is not None:
            self._event.set()


class GRPCConnectionCoroutine(ABC):  # pylint: disable=too-many-instance-attributes
    """
    gRPC connection coroutine
    """

    def __init__(self, agent, parent, name):
        super().__init__()
        logger.debug("Init: GRPC connection to %s", name)

        self.agent = agent
        self.connected = False
        self.data = None
        self.event = None
        self.hostname = agent.iams.prefix + name
        self.name = name
        self.parent = parent
        self.task = None

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<{self.__class__.__qualname__}({self.name})>"

    async def stop(self):
        """
        closes the connection and stops the coroutine
        """
        if self.task is not None and not self.task.done():
            self.task.cancel()
        if self.event is not None:
            self.event.set()

    async def start(self):
        """
        starts the coroutine
        """
        logger.debug("Start: GRPC connection to %s", self.name)
        if self.task is None:
            self.task = asyncio.create_task(self.main(), name=f"GRPCConnection.{self.name}")
        if self.event is None:
            self.event = asyncio.Event()

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

    @abstractmethod
    def grpc_method(self):
        """
        returns the default grpc method
        """

    @abstractmethod
    def grpc_payload(self):
        """
        returns the default grpc payload
        """

    @abstractmethod
    async def process(self, response):
        """
        process new data
        """

    async def disconnect(self):
        """
        disconnect callback
        """

    async def main(self):
        """
        manages the connection
        """
        wait = 0
        try:
            while True:
                try:
                    kwargs = {
                        'hostname': self.hostname,
                        'persistent': False,
                        'options': self.grpc_options(),
                    }

                    async with self.agent.grpc.stub(self.grpc_stub(), **kwargs) as stub:  # noqa: E501
                        method = getattr(stub, self.grpc_method())
                        payload = self.grpc_payload()
                        async for response in method(payload):
                            if not self.connected:
                                wait = 0
                                self.connected = True
                            self.data = response
                            await self.process(response)
                except grpc.RpcError as error:
                    logger.info(
                        "Connection rejected (%s) by %s: %s",
                        error.code(),  # pylint: disable=no-member
                        self.hostname,
                        error.details(),  # pylint: disable=no-member
                    )
                    self.connected = False
                    await self.disconnect()
                    wait = min(15, wait + 0.3)
                    await asyncio.sleep(wait)

        except asyncio.CancelledError:
            pass

        except Exception:
            logger.exception('Error in %s.main', self.__class__.__qualname__)
            raise
