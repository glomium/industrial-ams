#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.simulation import load_agent
# from iams.simulation import run_simulation
# from iams.simulation import prepare_data
# from iams.simulation import prepare_run
from iams.simulation import parse_command_line
# from iams.simulation import execute_command_line
from iams.simulation import *  # noqa


class SimulationTests(unittest.TestCase):

    def test_load_agent(self):
        result = list(load_agent(
            agents={},
            global_settings={'g': 1},
        ))
        self.assertEqual(result, [])

    def test_run_simulation(self):
        pass

    def test_prepare_data(self):
        pass

    def test_prepare_run(self):
        pass

    def test_parse_command_line(self):
        # no command line options
        with self.assertRaises(SystemExit):
            parse_command_line([])

    def test_execute_command_line(self):
        pass
