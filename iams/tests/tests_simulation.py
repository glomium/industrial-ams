#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.simulation
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

from iams.simulation import load_agent
# from iams.simulation import run_simulation
# from iams.simulation import prepare_data
from iams.simulation import process_config
from iams.simulation import parse_command_line
from iams.simulation import main


class Agent(object):
    def __init__(self, g, h=None):
        self.g = g
        self.h = h


class SimulationTests(unittest.TestCase):  # pragma: no cover

    def test_load_agent_empty(self):
        result = list(load_agent(
            agents=[],
            global_settings={'g': 1},
        ))
        self.assertEqual(result, [])

    def test_load_agent_single(self):
        result = list(load_agent(
            agents=[{
                'class': 'iams.tests.tests_simulation.Agent',
                'use_global': ['g'],
                'settings': {'h': 3},
            }],
            global_settings={'g': 1},
        ))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].g, 1)
        self.assertEqual(result[0].h, 3)

    def test_load_agent_multi(self):
        result = list(load_agent(
            agents=[{
                'class': 'iams.tests.tests_simulation.Agent',
                'use_global': ['g'],
                'permutations': {
                    'h': [2, 1],
                },
            }],
            global_settings={'g': 1},
        ))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].g, 1)
        self.assertEqual(result[1].g, 1)
        self.assertEqual(result[0].h, 1)
        self.assertEqual(result[1].h, 2)

    def test_wrong_file(self):
        with self.assertRaises(AssertionError):
            args = parse_command_line(['--dry-run', '-q', 'iams/tests/tests_simulation.py'])
            main(args)

    def test_config_no_simulation_class(self):
        with self.assertRaises(ValueError):
            list(process_config("/does/not/exist.yaml", {}, dryrun=True))

    def test_config_invalid_simulation_class1(self):
        with self.assertRaises(ModuleNotFoundError):
            list(process_config("/does/not/exist.yaml", {
                'simulation-class': 'iams.does_not_exist.Simulation',
            }, dryrun=True))

    def test_config_invalid_simulation_class2(self):
        with self.assertRaises(AssertionError):
            list(process_config("/does/not/exist.yaml", {
                'simulation-class': 'iams.interfaces.simulation.Queue',
            }, dryrun=True))

    def test_config_invalid_df_class1(self):
        with self.assertRaises(NotImplementedError):
            list(process_config("/does/not/exist.yaml", {
                'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
                'directory-facilitator': 'iams.interfaces.simulation.Queue',
            }, dryrun=True))

    def test_config_single(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
        }, dryrun=True))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "exist")

    def test_config_mulit1(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
            'permutations': {'a': [1, 2]},
        }, dryrun=True))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "exist-1")
        self.assertEqual(result[1]["name"], "exist-2")

    def test_config_mulit2(self):
        result = list(process_config("/does/not/exist.yaml", {
            'simulation-class': 'iams.tests.tests_interfaces_simulation.Simulation',
            'permutations': {'a': [2, 1]},
            'formatter': 'a-{a:d}',
        }, dryrun=True))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "exist-a-2")
        self.assertEqual(result[1]["name"], "exist-a-1")

    # def test_config_no_simulation_class(self):
    #     with self.assertRaises(ValueError):
    #         result = list(process_config("/does/not/exist.yaml", {
    #         }))
    #     self.assertEqual(result, None)
