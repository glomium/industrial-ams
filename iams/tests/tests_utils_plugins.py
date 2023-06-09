#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.plugins
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

from iams.utils.plugins import get_plugins


class PluginsTests(unittest.TestCase):  # pragma: no cover
    def test_iams_plugins(self):
        data = list(get_plugins())
        self.assertEqual(len(data), 7)
