#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams coroutine manager
"""

from time import time
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
        self.uptime = None
        self.timeout = 10.0

    def __call__(self, parent=None, executor=None):
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(self.exception_handler)
        logger.debug("Start Coroutine-Manager")
        loop.run_until_complete(self.main(parent, executor))
        logger.debug("Exit Coroutine-Manager")
        loop.close()

    async def main(self, parent, executor):  # pylint: disable=too-many-branches
        """
        main coroutine, providing a common eventloop for all related coroutines
        """
        logger.debug("Adding tasks for setup methods")
        tasks = set()
        for name, coro in self.coros.items():
            tasks.add(asyncio.create_task(coro.setup(executor), name=f"{name}.setup"))
        if hasattr(parent, "setup"):
            tasks.add(asyncio.create_task(parent.setup(executor), name="iams.agent.setup"))

        logger.debug("Start asyncio loop")
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        if pending:
            for task in pending:
                task.cancel()
            for task in done:
                exception = task.exception()
                if exception is not None:
                    logger.error("Exception raised from %r", task, exc_info=exception, stack_info=True)
            return None

        logger.debug("Adding tasks for start methods")
        starts = {}
        for name, coro in self.coros.items():
            starts[name] = asyncio.create_task(coro._start(), name=f"{name}.start")  # pylint: disable=protected-access

        logger.debug("Adding tasks for asyncio modules")
        tasks = set()
        for name, coro in self.coros.items():
            tasks.add(asyncio.create_task(coro(starts), name=f"{name}.call"))

        try:
            logger.debug("Start asyncio loop")
            self.uptime = time()
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except KeyboardInterrupt:  # pragma: no cover
            pending = tasks
            done = []
        else:
            logger.info("A Coroutine stopped - shutdown agent")

        # log the event that was closing the loop
        for task in done:
            exception = task.exception()
            if exception is None:
                logger.warning("%s finished without an exception", task.get_name())
            else:
                logger.error(
                    "Exception raised from coroutine %s",
                    task.get_name(), exc_info=exception, stack_info=True,
                )

        # send cancel events to all pending tasks
        for task in pending:
            logger.debug("Calling cancel on coroutine %s", task.get_name())
            task.cancel()

        try:
            for coro in asyncio.as_completed(pending, timeout=self.timeout):
                try:
                    await coro
                except Exception as exc:  # pylint: disable=broad-except
                    logger.info(
                        "Exception raised during cancel of a coroutine",
                        exc_info=exc,
                        stack_info=True,
                    )
        except asyncio.TimeoutError:
            logger.warning("Not all coroutines were cancelled within %.1f seconds", self.timeout)
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

    def get_uptime(self):
        """
        returns the time (in seconds) after the agent has booted
        """
        if self.uptime is None:
            return 0.0
        return time() - self.uptime

    def register(self, coro):
        """
        register coroutines with the manager
        """
        assert isinstance(coro, Coroutine)
        logger.debug("Register coroutine %s", coro)
        self.coros[str(coro)] = coro
