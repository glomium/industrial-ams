#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams coroutine interfaces
"""

from abc import ABC
from abc import abstractmethod
import asyncio
import logging


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
            logger.debug("%s received the cancel signal", self)
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
        periodic = True
        while not self._stop.done():
            try:
                async with self._lock:
                    await self.main(periodic=periodic)
                await asyncio.wait_for(self._event.wait(), timeout=self.get_interval())
            except asyncio.TimeoutError:
                periodic = True
            except asyncio.CancelledError:
                logger.debug("%r received the cancel signal", self)
                break
            except Exception:  # pylint: disable=broad-except
                logger.exception('Error executing main with periodic=%s', periodic)
                break
            else:
                periodic = False
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
