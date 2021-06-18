#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.agent
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

from unittest import mock
import os
import unittest

from google.protobuf.empty_pb2 import Empty
import grpc

from iams.agent import AgentBase
from iams.aio.interfaces import Coroutine
from iams.aio.grpc import GRPCCoroutine
from iams.aio.grpc import GRPCMixin
from iams.ca import CFSSL
from iams.proto import agent_pb2_grpc


cfssl = CFSSL("localhost:8888")
try:
    cfssl()
except Exception as exception:  # pylint: disable=broad-except # pragma: no cover
    SKIP = str(exception)
else:
    SKIP = None


class TestCoroutine(Coroutine):

    def __init__(self, grpc_servicer, case):
        self.case = case
        self.grpc = grpc_servicer

    async def loop(self):
        """
        loop method contains the business-code
        """

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        with self.case.subTest("ping"):
            await self.case.run_ping()

        with self.case.subTest("update"):
            await self.case.run_update()

        with self.case.subTest("upgrade"):
            await self.case.run_upgrade()

        with self.case.subTest("reset"):
            await self.case.run_reset()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """


class Agent(GRPCMixin, AgentBase):
    MAX_WORKERS = 2

    def __init__(self, case, root_certificate, private_key, certificate_chain) -> None:
        super().__init__()
        self.grpc = GRPCCoroutine(
            self, root_certificate=root_certificate, private_key=private_key,
            certificate_chain=certificate_chain, secret_folder=None,
            port=0,
        )
        self.response_update = True
        self.response_upgrade = True
        self.response_reset = True
        self.data = []
        self.aio_manager.register(TestCoroutine(self.grpc, case))

    async def callback_agent_upgrade(self):
        self.response_upgrade = not self.response_upgrade
        return self.response_upgrade

    async def callback_agent_update(self):
        self.response_update = not self.response_update
        return self.response_update

    async def callback_agent_reset(self):
        self.response_reset = not self.response_reset
        return self.response_reset


@unittest.skipIf(SKIP is not None, SKIP)
class AgentTests(unittest.TestCase):  # pragma: no cover

    def test_agent(self):
        root_certificate = cfssl.get_root_cert()
        certificate_chain, private_key = cfssl.get_agent_certificate("unittest")
        with mock.patch.dict(os.environ, {"IAMS_AGENT": "unittest", "IAMS_SERVICE": "localhost"}):
            # pylint: disable=attribute-defined-outside-init
            self.agent = Agent(self, root_certificate, private_key, certificate_chain)
            try:
                self.agent()
            except SystemExit:
                pass

    async def run_ping(self):
        async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
            stub = agent_pb2_grpc.AgentStub(channel)
            response = await stub.ping(
                Empty(),
                timeout=1,
            )
            self.assertEqual(response, Empty())

    async def run_update(self):
        self.assertEqual(self.agent.response_update, True)
        try:
            async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
                stub = agent_pb2_grpc.AgentStub(channel)
                response = await stub.update(
                    Empty(),
                    timeout=1,
                )
        except grpc.RpcError:
            self.assertEqual(self.agent.response_update, False)

        async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
            stub = agent_pb2_grpc.AgentStub(channel)
            response = await stub.update(
                Empty(),
                timeout=1,
            )

        self.assertEqual(self.agent.response_update, True)
        self.assertEqual(response, Empty())

    async def run_upgrade(self):
        self.assertEqual(self.agent.response_upgrade, True)
        try:
            async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
                stub = agent_pb2_grpc.AgentStub(channel)
                response = await stub.upgrade(
                    Empty(),
                    timeout=1,
                )
        except grpc.RpcError:
            self.assertEqual(self.agent.response_upgrade, False)

        async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
            stub = agent_pb2_grpc.AgentStub(channel)
            response = await stub.upgrade(
                Empty(),
                timeout=1,
            )

        self.assertEqual(self.agent.response_upgrade, True)
        self.assertEqual(response, Empty())

    async def run_reset(self):
        self.assertEqual(self.agent.response_reset, True)
        try:
            async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
                stub = agent_pb2_grpc.AgentStub(channel)
                response = await stub.reset(
                    Empty(),
                    timeout=1,
                )
        except grpc.RpcError:
            self.assertEqual(self.agent.response_reset, False)

        async with self.agent.grpc.channel(self.agent.grpc.manager, port=self.agent.grpc.port) as channel:
            stub = agent_pb2_grpc.AgentStub(channel)
            response = await stub.reset(
                Empty(),
                timeout=1,
            )

        self.assertEqual(self.agent.response_reset, True)
        self.assertEqual(response, Empty())
