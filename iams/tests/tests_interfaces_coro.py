#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unittests for iams.interfaces.coro
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import asyncio
import unittest

from iams.interfaces.coro import Coroutine
from iams.interfaces.coro import Manager


class CR1(Coroutine):

    def __init__(self, data):
        self.data = data

    async def loop(self):
        self.data.append("1loop")

    async def start(self):
        self.data.append("1start")

    async def stop(self):
        """
        not used
        """

    async def wait(self, setups):
        self.data.append("1wait")
        await asyncio.wait(setups.values())

    async def setup(self):
        self.data.append("1setup")


class CR2(Coroutine):

    def __init__(self, data):
        self.data = data

    async def loop(self):
        await asyncio.sleep(1.0)

    async def start(self):
        """
        not used
        """

    async def stop(self):
        self.data.append("2stop")

    async def wait(self, setups):
        self.data.append("2wait")

    async def setup(self):
        self.data.append("2setup")


class CoroTests(unittest.TestCase):  # pragma: no cover

    def test_single_coro(self):
        manager = Manager()
        data = list()

        cr1 = CR1(data)
        manager.register(cr1)
        manager()

        self.assertEqual(str(cr1), 'CR1')
        self.assertEqual(repr(cr1), 'CR1()')
        self.assertEqual(data, ["1setup", "1wait", "1start", "1loop"])

    def test_two_coro(self):
        data = list()
        manager = Manager()

        cr1 = CR1(data)
        cr2 = CR2(data)

        manager.register(cr1)
        manager.register(cr2)
        manager()

        self.assertEqual(data, ["1setup", "2setup", "2wait", "1wait", "1start", "1loop", "2stop"])
