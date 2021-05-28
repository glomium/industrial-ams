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


class Manager:
    """
    Coroutine manager
    """

    __hash__ = None

    def __init__(self):
        self.coros = {}
        self.loop = asyncio.new_event_loop()

    def __call__(self):
        setups = {}
        for name, coro in self.coros.items():
            setups[name] = self.loop.create_task(coro.setup())

        tasks = []
        for coro in self.coros.values():
            tasks.append(coro(setups))

        try:
            done, tasks = self.loop.run_until_complete(asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            ))
        except KeyboardInterrupt:  # pragma: no cover
            self.loop.close()
        else:
            logger.info("These tasks finished and the agent closes: %s", done)
            for task in tasks:
                task.cancel()
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        finally:
            logger.debug("Exit Coroutine-Manager")

    def register(self, coro):
        """
        register coroutines with the manager
        """
        self.coros[str(coro)] = coro


class Coroutine(ABC):
    """
    Coroutine Abstract Base Class
    """

    __hash__ = None

    async def __call__(self, setups):
        await self.wait(setups)
        await self.start()
        try:
            await self.loop()
        except asyncio.CancelledError:
            await self.stop()

    def __repr__(self):
        return f"{self.__class__.__qualname__}()"

    def __str__(self):
        return self.__class__.__qualname__

    async def setup(self):
        """
        setup method is awaited one at the start of the coroutines
        """

    @abstractmethod
    async def loop(self):
        """
        loop method contains the business-code
        """

    @abstractmethod
    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """

    @abstractmethod
    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """

    @abstractmethod
    async def wait(self, setups):
        """
        The wait method can be used to delay the startup of a coroutine until preconditions are fulfilled
        """
