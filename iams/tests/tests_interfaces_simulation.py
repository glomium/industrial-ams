#!/usr/bin/python
# ex:set fileencoding=utf-8:

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

    def __call__(self, simulation, dryrun):
        simulation.schedule(self, 0.5, 'callback')

    def callback(self, simulation):
        simulation.schedule(self, 0.5, 'callback')
        self.data += 1


class QueueTests(unittest.TestCase):  # pragma: no cover
    def test_str(self):
        queue = Queue(time=0.0, number=1, obj=None, callback='c', dt=0.0, args=[], kwargs={})
        self.assertEqual(str(queue), '0.0000:None:c')


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
        self.instance(
            dryrun=True,
            settings={},
        )
        self.assertEqual(agent.data, 2)

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
