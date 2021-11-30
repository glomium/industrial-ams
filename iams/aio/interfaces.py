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
            await self.stop()
        logger.debug("%s stopped", self)

    def __repr__(self):
        return f"{self.__class__.__qualname__}()"

    def __str__(self):
        return self.__class__.__qualname__

    @property
    def _loop(self):
        try:
            return getattr(self, '__loop')
        except AttributeError:
            logger.warning(
                "%s._loop should be cached in start by asyncio.get_running_loop()",
                self.__class__.__qualname__,
            )
            loop = asyncio.get_running_loop()
            setattr(self, '__loop', loop)
            return loop

    @_loop.setter
    def _loop(self, loop):
        setattr(self, '__loop', loop)

    async def setup(self, executor):
        """
        setup method is awaited once at the start of the coroutines
        """

    async def _start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        self._loop = asyncio.get_running_loop()
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
        self._stop = self._loop.create_future()

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

    async def _start(self):
        """
        setup method is awaited one at the start of the coroutines
        """
        super()._start()
        self._event = asyncio.Event()
        self._stop = self._loop.create_future()

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
                await asyncio.wait_for(self._event.wait(), timeout=self.INTERVAL)
            except asyncio.TimeoutError:
                periodic = True
            except asyncio.CancelledError:
                break
            else:
                periodic = False

            self._event.clear()
            await self.main(periodic=periodic)

    async def run(self):
        """
        redirects loop to a seperate task
        """
        self._event.set()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if self.stop is not None and not self._stop.done():
            self._stop.set_result(True)
        if self._event is not None:
            self._event.set()
