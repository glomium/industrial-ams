#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams coroutine manager
"""

import asyncio
import logging

from iams.aio.interfaces import Coroutine


logger = logging.getLogger(__name__)


class Manager:
    """
    Coroutine manager
    """

    __hash__ = None

    def __init__(self):
        self.coros = {}
        self.loop = asyncio.new_event_loop()

    def __call__(self, executor=None):
        setups = {}
        for name, coro in self.coros.items():
            setups[name] = self.loop.create_task(coro.setup(executor), name=f"{name}.setup")

        tasks = []
        for name, coro in self.coros.items():
            tasks.append(self.loop.create_task(coro(setups), name=f"{name}.main"))

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
        assert isinstance(coro, Coroutine)
        self.coros[str(coro)] = coro
