#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.server
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

from concurrent import futures
import unittest

from iams.server import Server
from iams.server import parse_command_line
from iams.tests.ca import CA
from iams.tests.df import DF
from iams.tests.runtime import Runtime


class Args:
    insecure_port = 0


class ServerTestCase(unittest.TestCase):  # pragma: no cover
    def setUp(self):
        self.threadpool = futures.ThreadPoolExecutor(max_workers=2)  # pylint: disable=consider-using-with
        server = Server(Args(), ca=CA(), df=DF(), runtime=Runtime())
        self.server = server(self.threadpool, secure=False)
        self.server.start()
        self.port = self.server.insecure_port

    def tearDown(self):
        self.server.stop()
        self.threadpool.shutdown()


class ServerTests(unittest.TestCase):  # pragma: no cover

    def test_parse_command_line(self):
        parse_command_line(["localhost:8888"])
