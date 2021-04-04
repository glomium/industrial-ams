#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.interfaces.simulation
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import io
import unittest

from iams.tests.df import DF
from iams.interfaces.simulation import Agent
from iams.interfaces.simulation import Queue
from iams.interfaces.simulation import SimulationInterface


class Simulation(SimulationInterface):

    def setup(self, **kwargs):
        pass

    def stop(self, dryrun):
        pass


class SimulationAgent(Agent):

    def __init__(self):
        self.data = 0

    def __str__(self):
        return 'test'

    def __call__(self, simulation, dryrun):
        event = simulation.schedule(self, 0.0, 'callback')
        simulation.schedule(self, 0.5, 'callback')
        event.cancel()

    def callback(self, simulation):
        simulation.schedule(self, 0.5, 'callback')
        self.data += 1

    def attributes(self):
        return {}

    def asdict(self):
        return {}


class AgentTests(unittest.TestCase):  # pragma: no cover
    def test_str(self):
        agent = SimulationAgent()
        self.assertEqual(str(agent), 'test')

    def test_hash(self):
        agent = SimulationAgent()
        self.assertEqual(hash(agent), hash('test'))

    def test_asdict(self):
        agent = SimulationAgent()
        self.assertEqual(agent.asdict(), {})


class QueueTests(unittest.TestCase):  # pragma: no cover
    def test_str(self):
        queue = Queue(time=0.0, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        self.assertEqual(str(queue), '0.0000:None:c')

    def test_cancel(self):
        queue = Queue(time=0.0, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        self.assertFalse(queue.deleted)
        queue.cancel()
        self.assertTrue(queue.deleted)

    def test_comparison(self):
        queue1 = Queue(time=0.0, obj=None, callback='c', dt=1.0, args=[], kwargs={})
        queue2 = Queue(time=0.0, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        queue3 = Queue(time=0.0, obj=None, callback='c', dt=1.0, priority="high", args=[], kwargs={})
        queue4 = Queue(time=1.0, obj=None, callback='c', dt=1.0, priority="high", args=[], kwargs={})
        queue5 = Queue(time=0.0, obj=None, callback='c', dt=1.0, priority="undefined", args=[], kwargs={})

        self.assertTrue(queue1 < queue2, "%r < %r" % (queue1, queue2))
        self.assertTrue(queue1 < queue3, "%r < %r" % (queue1, queue3))
        self.assertTrue(queue1 < queue4, "%r < %r" % (queue1, queue4))
        self.assertTrue(queue1 == queue5, "%r == %r" % (queue1, queue5))

        with self.assertRaises(NotImplementedError):
            queue1 < 'wrong_type'  # pylint: disable=pointless-statement
        with self.assertRaises(NotImplementedError):
            queue1 > 'wrong_type'  # pylint: disable=pointless-statement
        with self.assertRaises(NotImplementedError):
            queue1 != 'wrong_type'  # pylint: disable=pointless-statement
        with self.assertRaises(NotImplementedError):
            queue1 <= 'wrong_type'  # pylint: disable=pointless-statement
        with self.assertRaises(NotImplementedError):
            queue1 >= 'wrong_type'  # pylint: disable=pointless-statement
        with self.assertRaises(NotImplementedError):
            queue1 == 'wrong_type'  # pylint: disable=pointless-statement

        self.assertTrue(queue2 > queue1, "%r > %r" % (queue1, queue2))
        self.assertTrue(queue1 <= queue2, "%r <= %r" % (queue1, queue2))
        self.assertTrue(queue2 >= queue1, "%r >= %r" % (queue1, queue2))
        self.assertTrue(queue1 != queue2, "%r != %r" % (queue1, queue2))


class SimulationInterfaceTests(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.instance = Simulation(
            df=DF,
            name="name",
            folder="folder",
            fobj=io.StringIO(),
            seed=None,
            start=0,
            stop=1,
        )

    # def test_call(self):
    #     self.instance(
    #         dryrun=True,
    #         settings={},
    #     )
    #     agent = SimulationAgent()
    #     self.instance.register(agent)
    #     with self.assertRaises(KeyError):
    #         self.instance.register(agent)
    #     self.instance(
    #         dryrun=True,
    #         settings={},
    #     )
    #     self.assertEqual(len(self.instance._agents), 1)
    #     for a in self.instance.df.agents():
    #         self.assertEqual(a, agent)
    #     self.assertEqual(agent.data, 2)
    #     self.instance.unregister(agent)
    #     with self.assertRaises(KeyError):
    #         self.instance.unregister(agent)
    #     self.assertEqual(len(self.instance._agents), 0)

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

    def test_write_csv(self):
        self.instance.write_csv({'test': 1})
        self.instance.write_csv({'test': 2})
        self.instance._fobj.seek(0)
        written = self.instance._fobj.read()
        self.assertEqual(written, 'test\r\n1\r\n2\r\n')

    def test_get_time(self):
        self.assertEqual(self.instance.get_time(), 0.0)
