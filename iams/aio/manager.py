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
                logger.warning("%r finished without an exception", task)
            else:
                logger.error("Exception raised from task %r", task, exc_info=exception, stack_info=True)

        # send cancel events to all pending tasks
        for task in pending:
            logger.debug("Cancel %r", task)
            task.cancel()

        if pending:
            while True:
                logger.debug("Wait for %s coroutine(s) to be canceled", len(pending))
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    name = task.get_name()
                    try:
                        task.exception()
                    except asyncio.CancelledError as exception:  # pylint: disable=broad-except
                        logger.info(
                            "Exception raised during cancel of task %r",
                            name, exc_info=exception, stack_info=True,
                        )
                    else:
                        logger.debug("%r cancelled without an exception", name)

                if not pending:
                    break
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
