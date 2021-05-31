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
        logger.debug("Initialize asyncio manager")
        self.coros = {}
        self.loop = asyncio.new_event_loop()
        self.loop.set_exception_handler(self.exception_handler)

    def __call__(self, executor=None):
        logger.debug("Adding tasks for setup methods")
        setups = {}
        for name, coro in self.coros.items():
            coro._loop = self.loop
            setups[name] = self.loop.create_task(coro.setup(executor), name=f"{name}.setup")

        logger.debug("Adding tasks for asyncio modules")
        tasks = []
        for name, coro in self.coros.items():
            tasks.append(self.loop.create_task(coro(setups), name=f"{name}.main"))

        try:
            logger.debug("Start asyncio loop")
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

    @staticmethod
    def exception_handler(loop, context):  # pylint: disable=unused-argument
        """
        this handler logs all errors from asyncio
        """
        exception = context.get("exception", None)
        logger.debug("Exception in asyncio: %s", context, stack_info=True)
        if exception:
            logger.exception("Exception in asyncio: %s", exception, stack_info=True)
        # logger.exception("Exception in asyncio: %s", exception, stack_info=True)

    def register(self, coro):
        """
        register coroutines with the manager
        """
        assert isinstance(coro, Coroutine)
        logger.debug("Register coroutine %s", coro)
        self.coros[str(coro)] = coro
