#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import datetime

from iams.interfaces.scheduler import Event
from iams.interfaces.scheduler import States


class EventTests(unittest.TestCase):  # pragma: no cover
    def setUp(self):
        self.now = datetime.datetime(2000, 1, 1, 12, 0, 0)

    def test_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertTrue(event.use_datetime)
        self.assertEqual(event.get_eta(self.now), 0.0)
        event.set_etd(10, self.now)
        self.assertEqual(event.get_etd(self.now), 10.0)
        self.assertTrue(isinstance(event.etd, datetime.datetime))

    def test_integer(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertFalse(event.use_datetime)
        self.assertEqual(event.get_eta(), 0)
        event.set_eta(10)
        self.assertEqual(event.get_eta(), 10)
        self.assertTrue(isinstance(event.eta, int))

    def test_duration(self):
        event = Event(eta=0, duration=1, callback="callback")
        self.assertEqual(event.get_duration(), 1)

    def test_event_schedule(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.schedule()
        self.assertEqual(event.state, States.SCHEDULED)

    def test_event_arrive(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.arrive()
        self.assertEqual(event.state, States.ARRIVED)

    def test_event_start(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.start()
        self.assertEqual(event.state, States.STARTED)

    def test_event_finish(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.finish()
        self.assertEqual(event.state, States.FINISHED)

    def test_event_depart(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.depart()
        self.assertEqual(event.state, States.DEPARTED)

    def test_event_cancel(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.cancel()
        self.assertEqual(event.state, States.CANCELED)

    def test_getter_setter(self):
        event = Event(eta=0, duration=0, callback="callback")

        for name in ["eta_max", "eta_min", "etd_max", "etd_min", "start", "finish"]:
            with self.subTest(name=name):
                getter = getattr(event, f"get_{name}")
                setter = getattr(event, f"set_{name}")
                self.assertEqual(getter(), None)
                setter(10)
                self.assertEqual(getter(), 10)
