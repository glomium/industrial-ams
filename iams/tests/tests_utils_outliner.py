#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.outliner
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest


try:
    from iams.utils.outliner import quartiles
except ImportError as e:  # pragma: no cover
    SKIP = str(e)
else:
    SKIP = None


@unittest.skipIf(SKIP is not None, SKIP)
class QuartilesTests(unittest.TestCase):  # pragma: no cover

    def test_dataset1(self):
        x = [1]
        a, b, c, d, e = quartiles(x)
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 1.0)
        self.assertEqual(c, 1.0)
        self.assertEqual(d, 1.0)
        self.assertEqual(e, 1.0)

    def test_dataset2(self):
        x = [0, 1, 2, 2]
        a, b, c, d, e = quartiles(x, whiskers=0.0)
        self.assertEqual(a, 0.75)
        self.assertEqual(b, 0.75)
        self.assertEqual(c, 1.5)
        self.assertEqual(d, 2.0)
        self.assertEqual(e, 2.0)

    def test_dataset3(self):
        x = [1, 1, 2, 3]
        a, b, c, d, e = quartiles(x, whiskers=0.0)
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 1.0)
        self.assertEqual(c, 1.5)
        self.assertEqual(d, 2.25)
        self.assertEqual(e, 2.25)
