#!/usr/bin/python
# ex:set fileencoding=utf-8:
"""
unittests for iams.interfaces.runtime
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

from iams.interfaces.plugin import Plugin
from iams.tests.runtime import Runtime


class TestPlugin(Plugin):

    @classmethod
    def label(cls):
        return None


class ImportTests(unittest.TestCase):

    def setUp(self):
        self.runtime = Runtime()

    def test_register_plugin(self):
        with self.assertRaises(AssertionError):
            self.runtime.register_plugin(object)

        self.runtime.register_plugin(TestPlugin(None, None))
