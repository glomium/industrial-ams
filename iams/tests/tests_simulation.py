#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.simulation import load_agent
# from iams.simulation import run_simulation
# from iams.simulation import prepare_data
from iams.simulation import process_config
from iams.simulation import parse_command_line
from iams.simulation import execute_command_line


class SimulationTests(unittest.TestCase):

    def test_load_agent(self):
        result = list(load_agent(
            agents={},
            global_settings={'g': 1},
        ))
        self.assertEqual(result, [])

    def test_wrong_file(self):
        with self.assertRaises(AssertionError):
            args = parse_command_line(['--dry-run', '-q', 'iams/tests/tests_simulation.py'])
            execute_command_line(args)

    def test_config_no_simulation_class(self):
        with self.assertRaises(ValueError):
            list(process_config("/does/not/exist.yaml", {
            }))

    def test_config_invalid_simulation_class1(self):
        with self.assertRaises(ModuleNotFoundError):
            list(process_config("/does/not/exist.yaml", {
                'simulation-class': 'iams.does_not_exist.Simulation',
            }))

    def test_config_invalid_simulation_class2(self):
        with self.assertRaises(AssertionError):
            list(process_config("/does/not/exist.yaml", {
                'simulation-class': 'iams.interfaces.simulation.Queue',
            }))

    def test_config_single(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
        }))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "exist")

    def test_config_mulit1(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
            'permutations': {'a': [1, 2]},
        }))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "exist-1")
        self.assertEqual(result[1]["name"], "exist-2")

    def test_config_mulit2(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
            'permutations': {'a': [2, 1]},
            'formatter': 'a-{a:d}',
        }))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "exist-a-2")
        self.assertEqual(result[1]["name"], "exist-a-1")

    # def test_config_no_simulation_class(self):
    #     with self.assertRaises(ValueError):
    #         result = list(process_config("/does/not/exist.yaml", {
    #         }))
    #     self.assertEqual(result, None)
