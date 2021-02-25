#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.interfaces.plugin import Plugin
from iams.interfaces.runtime import RuntimeInterface


class TestPlugin(Plugin):

    @classmethod
    def label(cls):
        return None


class Runtime(RuntimeInterface):

    def get_agent_plugins(self, name):
        pass

    def get_agent_config(self, name):
        pass

    def delete_agent(self, name):
        pass

    def delete_agent_secrets(self, name):
        pass

    def delete_agent_configs(self, name):
        pass

    def update_agent(self, request, create=False, update=False):
        pass


class ImportTests(unittest.TestCase):

    def setUp(self):
        self.runtime = Runtime()

    def test_register_plugin(self):
        with self.assertRaises(AssertionError):
            self.runtime.register_plugin(object)

        self.runtime.register_plugin(TestPlugin(None, None))
