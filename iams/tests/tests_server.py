#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.server
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

# from iams.server import Server
from iams.server import parse_command_line


class ServerTests(unittest.TestCase):  # pragma: no cover
    def test_parse_command_line(self):
        parse_command_line(["localhost:8888"])
