#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.interfaces.scheduler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,too-many-public-methods  # noqa

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

    def test_eta_tuple1(self):
        event = Event(eta=[1], duration=0, callback="callback")
        self.assertEqual(event.get_eta(), 1)
        self.assertEqual(event.get_eta_min(), None)
        self.assertEqual(event.get_eta_max(), None)

    def test_eta_tuple2(self):
        event = Event(eta=[1, 2], duration=0, callback="callback")
        self.assertEqual(event.get_eta(), None)
        self.assertEqual(event.get_eta_min(), 1)
        self.assertEqual(event.get_eta_max(), 2)

    def test_eta_tuple3(self):
        event = Event(eta=[1, 2, 3], duration=0, callback="callback")
        self.assertEqual(event.get_eta(), 2)
        self.assertEqual(event.get_eta_min(), 1)
        self.assertEqual(event.get_eta_max(), 3)

    def test_eta_tuple4(self):
        with self.assertRaises(ValueError):
            Event(eta=[1, 2, 3, 4], duration=0, callback="callback")

    def test_etd_tuple1(self):
        event = Event(eta=0, etd=[1], duration=0, callback="callback")
        self.assertEqual(event.get_etd(), 1)
        self.assertEqual(event.get_etd_min(), None)
        self.assertEqual(event.get_etd_max(), None)

    def test_etd_tuple2(self):
        event = Event(eta=0, etd=[1, 2], duration=0, callback="callback")
        self.assertEqual(event.get_etd(), None)
        self.assertEqual(event.get_etd_min(), 1)
        self.assertEqual(event.get_etd_max(), 2)

    def test_etd_tuple3(self):
        event = Event(eta=0, etd=[1, 2, 3], duration=0, callback="callback")
        self.assertEqual(event.get_etd(), 2)
        self.assertEqual(event.get_etd_min(), 1)
        self.assertEqual(event.get_etd_max(), 3)

    def test_etd_tuple4(self):
        with self.assertRaises(ValueError):
            Event(eta=0, etd=[1, 2, 3, 4], duration=0, callback="callback")

    def test_event_schedule(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.schedule(0, 10)
        self.assertEqual(event.state, States.SCHEDULED)

    def test_event_schedule_error(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        with self.assertRaises(AssertionError):
            event.schedule(10, 0)

    def test_event_arrive_nodatetime(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.arrive(0)
        self.assertEqual(event.state, States.ARRIVED)

    def test_event_arrive_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.arrive(self.now)
        self.assertEqual(event.state, States.ARRIVED)

    def test_event_start(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.start(0)
        self.assertEqual(event.state, States.STARTED)

    def test_event_start_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.start(self.now)
        self.assertEqual(event.state, States.STARTED)

    def test_event_finish(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.finish(0)
        self.assertEqual(event.state, States.FINISHED)

    def test_event_finish_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.finish(self.now)
        self.assertEqual(event.state, States.FINISHED)

    def test_event_depart(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.depart(0)
        self.assertEqual(event.state, States.DEPARTED)

    def test_event_depart_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.depart(self.now)
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
