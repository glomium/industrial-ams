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

    def test_hash(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertEqual(hash(event), hash(0))

    def test_comparison_eq(self):
        event1 = Event(eta=0, duration=0, callback="callback")
        event2 = Event(eta=1, duration=0, callback="callback")
        self.assertEqual(event1, event2)
        event1.uid = 1
        event2.uid = 2
        self.assertNotEqual(event1, event2)

    def test_comparison_lt(self):
        event1 = Event(eta=0, duration=0, callback="callback")
        event2 = Event(eta=1, duration=0, callback="callback")
        event1.uid = 1
        event2.uid = 2
        self.assertTrue(event1 < event2)
        event2.start(1)
        self.assertTrue(event2 < event1)
        event1.start(0)
        self.assertTrue(event1 < event2)
        event1.finish(0)
        event2.finish(1)
        self.assertTrue(event1 < event2)
        event1.depart(0)
        event2.depart(1)
        self.assertTrue(event1 < event2)

        with self.assertRaises(NotImplementedError):
            event1 < "asd"  # pylint: disable=pointless-statement

    def test_comparison_le(self):
        event1 = Event(eta=0, duration=0, callback="callback")
        event2 = Event(eta=1, duration=0, callback="callback")
        event1.uid = 1
        event2.uid = 2
        self.assertTrue(event1 <= event2)
        event2.start(1)
        self.assertTrue(event2 <= event1)
        event1.start(0)
        self.assertTrue(event1 <= event2)
        event1.finish(0)
        event2.finish(1)
        self.assertTrue(event1 <= event2)
        event1.depart(0)
        event2.depart(1)
        self.assertTrue(event1 <= event2)

        with self.assertRaises(NotImplementedError):
            event1 <= "asd"  # pylint: disable=pointless-statement

    def test_comparison_ge(self):
        event1 = Event(eta=0, duration=0, callback="callback")
        event2 = Event(eta=1, duration=0, callback="callback")
        event1.uid = 1
        event2.uid = 2
        self.assertTrue(event2 >= event1)
        event2.start(1)
        self.assertTrue(event1 >= event2)
        event1.start(0)
        self.assertTrue(event2 >= event1)
        event1.finish(0)
        event2.finish(1)
        self.assertTrue(event2 >= event1)
        event1.depart(0)
        event2.depart(1)
        self.assertTrue(event2 >= event1)

        with self.assertRaises(NotImplementedError):
            event1 >= "asd"  # pylint: disable=pointless-statement

    def test_comparison_gt(self):
        event1 = Event(eta=0, duration=0, callback="callback")
        event2 = Event(eta=1, duration=0, callback="callback")
        event1.uid = 1
        event2.uid = 2
        self.assertTrue(event2 > event1)
        event2.start(1)
        self.assertTrue(event1 > event2)
        event1.start(0)
        self.assertTrue(event2 > event1)
        event1.finish(0)
        event2.finish(1)
        self.assertTrue(event2 > event1)
        event1.depart(0)
        event2.depart(1)
        self.assertTrue(event2 > event1)

        with self.assertRaises(NotImplementedError):
            event1 > "asd"  # pylint: disable=pointless-statement

    def test_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertTrue(event.use_datetime)

        lower, upper = event.eta_constraints()
        self.assertEqual(lower, self.now)
        self.assertEqual(upper, self.now)
        lower, upper = event.eta_constraints(self.now)
        self.assertEqual(lower, 0.0)
        self.assertEqual(upper, 0.0)

        event.etd.set(10, self.now)
        lower, upper = event.etd_constraints(self.now)
        self.assertEqual(event.etd.get(self.now), 10.0)
        self.assertTrue(isinstance(event.etd.get(), datetime.datetime))

    def test_integer(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertFalse(event.use_datetime)
        self.assertEqual(event.eta, 0)
        event.etd.set(10)
        self.assertEqual(event.etd, 10)
        self.assertTrue(isinstance(event.etd.get(), int))

    def test_eta_tuple1(self):
        event = Event(eta=[1], duration=0, callback="callback")
        self.assertEqual(event.eta.constraint_low, 1)
        self.assertEqual(event.eta.constraint_high, 1)

    def test_eta_tuple2(self):
        event = Event(eta=[1, 2], duration=0, callback="callback")
        self.assertEqual(event.eta.constraint_low, 1)
        self.assertEqual(event.eta.constraint_high, 2)

    def test_eta_tuple3(self):
        event = Event(eta=[1, 2, 3], duration=0, callback="callback")
        self.assertEqual(event.eta, 2)
        self.assertEqual(event.eta.constraint_low, 1)
        self.assertEqual(event.eta.constraint_high, 3)

    def test_eta_tuple4(self):
        with self.assertRaises(ValueError):
            Event(eta=[1, 2, 3, 4], duration=0, callback="callback")

    def test_eta_none(self):
        with self.assertRaises(ValueError):
            Event(eta=None, duration=0, callback="callback")
        with self.assertRaises(ValueError):
            Event(eta=[None], duration=0, callback="callback")
        with self.assertRaises(ValueError):
            Event(eta=[0, None], duration=0, callback="callback")
        with self.assertRaises(ValueError):
            Event(eta=[None, 0], duration=0, callback="callback")

    def test_wrong_type(self):
        with self.assertRaises(ValueError):
            Event(eta='wrong', duration=0, callback="callback")

    def test_wrong_type_datetime(self):
        with self.assertRaises(ValueError):
            Event(eta=[0, self.now, 10], duration=0, callback="callback")

    def test_etd_tuple1(self):
        for etd in [[1], [None]]:
            with self.subTest(etd=etd):
                event = Event(eta=0, etd=etd, duration=0, callback="callback")
                self.assertEqual(event.etd.constraint_low, etd[0])
                self.assertEqual(event.etd.constraint_high, etd[0])
                if etd[0] is None:
                    self.assertEqual(event.state, States.NEW)
                else:
                    self.assertEqual(event.state, States.SCHEDULED)

    def test_etd_tuple2(self):
        for etd in [[1, 2], [1, None], [None, 2], [None, None]]:
            with self.subTest(etd=etd):
                event = Event(eta=0, etd=etd, duration=0, callback="callback")
                self.assertEqual(event.etd.constraint_low, etd[0])
                self.assertEqual(event.etd.constraint_high, etd[1])
                if etd[0] is not None and etd[1] is not None:
                    self.assertEqual(event.state, States.SCHEDULED)
                else:
                    self.assertEqual(event.state, States.NEW)

    def test_etd_tuple3(self):
        for etd in [[1, 2, 3], [1, 2, None], [None, 2, 3], [None, None, None]]:
            with self.subTest(etd=etd):
                event = Event(eta=0, etd=etd, duration=0, callback="callback")
                self.assertEqual(event.etd.get(), etd[1])
                self.assertEqual(event.etd.constraint_low, etd[0])
                self.assertEqual(event.etd.constraint_high, etd[2])
                if etd[0] is not None and etd[2] is not None:
                    self.assertEqual(event.state, States.SCHEDULED)
                else:
                    self.assertEqual(event.state, States.NEW)

    def test_etd_tuple4(self):
        with self.assertRaises(ValueError):
            Event(eta=0, etd=[1, 2, 3, 4], duration=0, callback="callback")

    def test_schedule_tuple2(self):
        etd = [1, 2]
        event = Event(eta=0, duration=0, callback="callback")
        event.schedule_etd(etd[0], etd[1])
        self.assertEqual(event.etd.get(), None)
        self.assertEqual(event.etd.constraint_low, etd[0])
        self.assertEqual(event.etd.constraint_high, etd[1])
        self.assertEqual(event.state, States.SCHEDULED)

    def test_schedule_invalid_datetime(self):
        etd = [self.now, 1]
        with self.assertRaises(TypeError):
            event = Event(eta=self.now, duration=0, callback="callback")
            event.schedule_etd(etd[0], etd[1])

    def test_schedule_etd_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertTrue(event.use_datetime)
        event.schedule_etd(self.now, self.now)
        self.assertEqual(event.etd.get(), None)
        self.assertEqual(event.etd.constraint_low, self.now)
        self.assertEqual(event.etd.constraint_high, self.now)

    def test_schedule_wrong_type1(self):
        with self.assertRaises(TypeError):
            event = Event(eta=0, duration=0, callback="callback")
            self.assertFalse(event.use_datetime)
            event.schedule_etd(self.now)

    def test_schedule_wrong_type2(self):
        with self.assertRaises(TypeError):
            event = Event(eta=self.now, duration=0, callback="callback")
            self.assertTrue(event.use_datetime)
            event.schedule_etd(1)

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

    def test_event_cancel1(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.cancel()
        self.assertEqual(event.state, States.CANCELED)
        self.assertTrue(event.canceled)

    def test_event_cancel2(self):
        event = Event(eta=0, duration=0, callback="callback")
        self.assertEqual(event.state, States.NEW)
        event.start(0)
        event.cancel()
        self.assertEqual(event.state, States.STARTED)
        self.assertTrue(event.canceled)

    def test_getter_setter(self):
        event = Event(eta=0, duration=0, callback="callback")

        for name in ["start", "finish"]:
            with self.subTest(name=name):
                getter = getattr(event, f"get_{name}")
                setter = getattr(event, f"set_{name}")
                self.assertEqual(getter(), None)
                setter(10)
                self.assertEqual(getter(), 10)
