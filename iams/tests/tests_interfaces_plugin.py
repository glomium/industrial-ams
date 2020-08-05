#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.interfaces.plugin import Plugin  # noqa


class TestPlugin(Plugin):

    @classmethod
    def label(cls):
        return "Test"


class Tests(unittest.TestCase):
    def test_all(self):
        plugin = TestPlugin('namespace', False)
        self.assertEqual(plugin.namespace, 'namespace')
        self.assertEqual(plugin.simulation, False)
        self.assertEqual(repr(plugin), "TestPlugin(namespace)")
        self.assertEqual(
            plugin("name", "image", "version", "config"),
            ({}, {}, set(), {}, []),
        )
        self.assertIsNone(plugin.remove("name", "config"))
