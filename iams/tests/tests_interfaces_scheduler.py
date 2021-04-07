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
                self.assertEqual(event.get_etd(), etd[0])
                self.assertEqual(event.get_etd_min(), None)
                self.assertEqual(event.get_etd_max(), None)
                self.assertEqual(event.state, States.NEW)

    def test_etd_tuple2(self):
        for etd in [[1, 2], [1, None], [None, 2], [None, None]]:
            with self.subTest(etd=etd):
                event = Event(eta=0, etd=etd, duration=0, callback="callback")
                self.assertEqual(event.get_etd(), None)
                self.assertEqual(event.get_etd_min(), etd[0])
                self.assertEqual(event.get_etd_max(), etd[1])
                if etd[0] is not None and etd[1] is not None:
                    self.assertEqual(event.state, States.SCHEDULED)
                else:
                    self.assertEqual(event.state, States.NEW)

    def test_etd_tuple3(self):
        for etd in [[1, 2, 3], [1, 2, None], [None, 2, 3], [None, None, None]]:
            with self.subTest(etd=etd):
                event = Event(eta=0, etd=etd, duration=0, callback="callback")
                self.assertEqual(event.get_etd(), etd[1])
                self.assertEqual(event.get_etd_min(), etd[0])
                self.assertEqual(event.get_etd_max(), etd[2])
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
        event.schedule(etd)
        self.assertEqual(event.get_etd(), None)
        self.assertEqual(event.get_etd_min(), etd[0])
        self.assertEqual(event.get_etd_max(), etd[1])
        self.assertEqual(event.state, States.SCHEDULED)

    def test_schedule_tuple3(self):
        etd = [1, 2, 3]
        event = Event(eta=0, duration=0, callback="callback")
        event.schedule(etd)
        self.assertEqual(event.get_etd(), etd[1])
        self.assertEqual(event.get_etd_min(), etd[0])
        self.assertEqual(event.get_etd_max(), etd[2])
        self.assertEqual(event.state, States.SCHEDULED)

    def test_schedule_invalid(self):
        for etd in [1, [1], [None, None], [None, None, None], [1, None], [None, 2], [1, 2, 3, 4]]:
            with self.subTest(etd=etd), self.assertRaises(ValueError):
                event = Event(eta=0, duration=0, callback="callback")
                event.schedule(etd)

    def test_schedule_invalid_datetime(self):
        etd = [self.now, 1]
        with self.assertRaises(ValueError):
            event = Event(eta=self.now, duration=0, callback="callback")
            event.schedule(etd)

    def test_schedule_etd_use_from_event(self):
        event = Event(eta=0, etd=[1, 3], duration=0, callback="callback")
        event.schedule([0, 4])
        self.assertEqual(event.get_etd_min(), 1)
        self.assertEqual(event.get_etd_max(), 3)

    def test_schedule_etd_max_small(self):
        with self.assertRaises(ValueError):
            event = Event(eta=0, duration=0, callback="callback")
            event.schedule([1, 2, 1])

    def test_schedule_etd_min_large(self):
        with self.assertRaises(ValueError):
            event = Event(eta=0, duration=0, callback="callback")
            event.schedule([3, 2, 3])

    def test_schedule_datetime(self):
        event = Event(eta=self.now, duration=0, callback="callback")
        self.assertTrue(event.use_datetime)
        event.schedule([self.now, self.now])
        self.assertEqual(event.etd, None)
        self.assertEqual(event.etd_min, self.now)
        self.assertEqual(event.etd_max, self.now)

    def test_schedule_wrong_type1(self):
        with self.assertRaises(ValueError):
            event = Event(eta=0, duration=0, callback="callback")
            self.assertFalse(event.use_datetime)
            event.schedule(self.now)

    def test_schedule_wrong_type2(self):
        with self.assertRaises(ValueError):
            event = Event(eta=self.now, duration=0, callback="callback")
            self.assertTrue(event.use_datetime)
            event.schedule(1)

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

        for name in ["eta_max", "eta_min", "etd_max", "etd_min", "start", "finish"]:
            with self.subTest(name=name):
                getter = getattr(event, f"get_{name}")
                setter = getattr(event, f"set_{name}")
                self.assertEqual(getter(), None)
                setter(10)
                self.assertEqual(getter(), 10)
