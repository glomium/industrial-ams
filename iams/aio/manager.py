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

    def __call__(self, parent=None, executor=None):  # pylint: disable=too-many-branches
        logger.debug("Adding tasks for setup methods")
        tasks = set()
        for name, coro in self.coros.items():
            tasks.add(self.loop.create_task(coro.setup(executor), name=f"{name}.setup"))
        if hasattr(parent, "setup"):
            tasks.add(self.loop.create_task(parent.setup(executor), name="iams.agent.setup"))

        logger.debug("Start asyncio loop")
        done, _ = self.loop.run_until_complete(asyncio.wait(tasks))

        for task in done:
            exception = task.exception()
            if exception is not None:
                logger.error("Exception raised from task %s", task, exc_info=exception, stack_info=True)
                return None

        logger.debug("Adding tasks for start methods")
        starts = {}
        for name, coro in self.coros.items():
            starts[name] = self.loop.create_task(coro._start(), name=f"{name}.start")

        logger.debug("Adding tasks for asyncio modules")
        tasks = set()
        for name, coro in self.coros.items():
            task = self.loop.create_task(coro(starts), name=f"{name}.main")
            coro._task = task
            tasks.add(task)

        try:
            logger.debug("Start asyncio loop")
            done, tasks = self.loop.run_until_complete(asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            ))
        except KeyboardInterrupt:  # pragma: no cover
            self.loop.close()
        else:
            logger.info("A Coroutine stopped - shutdown agent")

            for task in tasks:
                task.cancel()

            for task in done:
                exception = task.exception()
                if exception is None:
                    logger.warning("The task %s finished without an exception", task)
                else:
                    logger.error("Exception raised from task %s", task, exc_info=exception, stack_info=True)

            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        finally:
            logger.debug("Exit Coroutine-Manager")
        return None

    @staticmethod
    def exception_handler(loop, context):  # pylint: disable=unused-argument
        """
        this handler logs all errors from asyncio
        """
        exception = context.get("exception", None)
        if exception:
            logger.info("Exception in asyncio", exc_info=exception, stack_info=True)
        else:
            logger.debug("Exception in asyncio", stack_info=True)

    def register(self, coro):
        """
        register coroutines with the manager
        """
        assert isinstance(coro, Coroutine)
        logger.debug("Register coroutine %s", coro)
        self.coros[str(coro)] = coro
