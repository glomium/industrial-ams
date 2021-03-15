#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import unittest

from iams.interfaces.simulation import Queue
from iams.interfaces.simulation import SimulationInterface


class Simulation(SimulationInterface):

    def setup(self, **kwargs):
        pass

    def stop(self, dryrun):
        pass


class Agent(object):

    def __init__(self):
        self.data = 0

    def __str__(self):
        return "agent"

    def __call__(self, simulation, dryrun):
        event = simulation.schedule(self, 0.0, 'callback')
        simulation.schedule(self, 0.5, 'callback')
        event.cancel()

    def callback(self, simulation):
        simulation.schedule(self, 0.5, 'callback')
        self.data += 1


class QueueTests(unittest.TestCase):  # pragma: no cover
    def test_str(self):
        queue = Queue(time=0.0, number=1, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        self.assertEqual(str(queue), '0.0000:None:c')

    def test_cancel(self):
        queue = Queue(time=0.0, number=1, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        self.assertFalse(queue.deleted)
        queue.cancel()
        self.assertTrue(queue.deleted)


class SimulationInterfaceTests(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.instance = Simulation(
            df=None,
            name="name",
            folder="folder",
            fobj=io.StringIO(),
            seed=None,
            start=0,
            stop=1,
        )

    def test_call(self):
        self.instance(
            dryrun=True,
            settings={},
        )
        agent = Agent()
        self.instance.register(agent)
        with self.assertRaises(KeyError):
            self.instance.register(agent)
        self.instance(
            dryrun=True,
            settings={},
        )
        self.assertEqual(len(self.instance._agents), 1)
        for a in self.instance.agents():
            self.assertEqual(a, agent)
        self.assertEqual(agent.data, 2)
        self.instance.unregister(agent)
        with self.assertRaises(KeyError):
            self.instance.unregister(agent)
        self.assertEqual(len(self.instance._agents), 0)

    def test_str(self):
        self.assertEqual(str(self.instance), 'Simulation(name)')

    def test_schedule(self):
        self.assertEqual(len(self.instance._queue), 0)
        self.instance.schedule(None, 0.0, 'cb')
        self.assertEqual(len(self.instance._queue), 1)

    def test_write(self):
        self.instance.write('test')
        self.instance._fobj.seek(0)
        written = self.instance._fobj.read()
        self.assertEqual(written, 'test')

    def test_write_json(self):
        self.instance.write_json('test')
        self.instance._fobj.seek(0)
        written = self.instance._fobj.read()
        self.assertEqual(written, '"test"\n')

    def test_get_time(self):
        self.assertEqual(self.instance.get_time(), 0.0)