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
        if hasattr(self, '__loop'):
            return getattr(self, '__loop')
        logger.warning("%s._loop should be set", self.__class__.__qualname__)
        return asyncio.get_running_loop()

    @_loop.setter
    def _loop(self, loop):
        setattr(self, '__loop', loop)

    @property
    def _task(self):
        if hasattr(self, '__task'):
            return getattr(self, '__task')
        logger.warning("%s._task should be set", self.__class__.__qualname__)
        return None

    @_task.setter
    def _task(self, task):
        setattr(self, '__task', task)

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """

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
