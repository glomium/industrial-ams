#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from iams.tests.scheduler import TestScheduler


class ImportTests(unittest.TestCase):  # pragma: no cover
    def test_empty(self):
        TestScheduler(None)