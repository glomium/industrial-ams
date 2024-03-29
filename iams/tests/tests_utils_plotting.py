#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.auth
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

try:
    from iams.utils.plotting import PlotInterface
except Exception as exception:  # pylint: disable=broad-except # pragma: no cover
    SKIP = str(exception)
else:
    SKIP = None

    class Plot(PlotInterface):
        """
        Test plots
        """
        def parameters(self, name):
            return {'test': True}

        @staticmethod
        def iterator_individual_plots():
            yield plot_individual1
            yield plot_individual2

        @staticmethod
        def iterator_aggregated_plots():
            yield plot_aggregated


def plot_individual1(basename, parameters, dataframe):  # pylint: disable=unused-argument
    """
    plot on individual dataset
    """


def plot_individual2(basename, parameters, dataframe):  # pylint: disable=unused-argument
    """
    plot on individual dataset
    """
    return {'test': 2}


def plot_aggregated(dataframe):  # pylint: disable=unused-argument
    """
    plot on aggregated dataframes
    """


@unittest.skipIf(SKIP is not None, SKIP)
class PlotTests(unittest.TestCase):  # pragma: no cover

    @unittest.expectedFailure
    def test_empty(self):
        Plot()
