#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.scheduler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,too-many-public-methods  # noqa

from itertools import permutations
# from operator import attrgetter
import unittest

from iams.exceptions import CanNotSchedule
from iams.interfaces import SchedulerState

try:
    from iams.utils.scheduler import BufferScheduler
except ImportError as exception:  # pragma: no cover
    SKIP = str(exception)
else:
    SKIP = None


@unittest.skipIf(SKIP is not None, SKIP)
class BufferSchedulerTests(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.scheduler = BufferScheduler(agent="simulation", horizon=30)

    def test_repr(self):
        self.assertEqual(
            repr(self.scheduler),
            "<BufferScheduler(horizon=30, buffer_input=[1], buffer_output=[1])>",
        )

    def test_one_event_full(self):
        scheduler = BufferScheduler(agent="simulation", horizon=10)
        event = scheduler(eta=0, duration=1, callback=None)

        with self.subTest("new"):
            self.assertTrue(scheduler.can_schedule(event))
            self.assertTrue(scheduler.save(event))
            self.assertEqual(event.state, SchedulerState.NEW)
            self.assertEqual(event.eta, 0)
            self.assertTrue(scheduler.validate())

        with self.subTest("scheduled"):
            event.schedule_etd(1, 1)
            self.assertTrue(scheduler.validate())
            self.assertEqual(event.state, SchedulerState.SCHEDULED)
            self.assertEqual(event.etd, 1)

        with self.subTest("arrive"):
            event.arrive(0)
            self.assertTrue(scheduler.validate())
            self.assertEqual(event.state, SchedulerState.ARRIVED)

        with self.subTest("start"):
            event.start(0)
            self.assertTrue(scheduler.validate())
            self.assertEqual(event.state, SchedulerState.STARTED)

        with self.subTest("finish"):
            event.finish(1)
            self.assertTrue(scheduler.validate())
            self.assertEqual(event.state, SchedulerState.FINISHED)

        with self.subTest("depart"), self.assertRaises(NotImplementedError):
            event.depart(1)
            self.scheduler.can_schedule(event)

    def test_event_too_long(self):
        event = self.scheduler(eta=0, etd=[1, 1], duration=2, callback=None)
        with self.assertRaises(CanNotSchedule):
            self.assertEqual(event.state, SchedulerState.SCHEDULED)
            self.scheduler.can_schedule(event)

    def test_schedule_one_single_eta(self):
        event = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event)
        self.assertTrue(result)

        self.assertEqual(event.eta, 0)
        self.assertEqual(event.get_start(), 0)
        self.assertEqual(event.get_finish(), 2)
        self.assertEqual(event.etd, 2)
        self.assertEqual(event.duration, 2)

    def test_schedule_horizon_shifted(self):
        event_data = [
            {'eta': (106, 106, 106), 'duration': 13, 'callback': None},
            {'eta': (127, 127, 127), 'duration': 11, 'callback': None},
        ]
        scheduler = BufferScheduler(agent="simulation", horizon=40, buffer_input=1)

        event1 = scheduler(**event_data[0])
        scheduler.can_schedule(event1)
        scheduler.save(event1)
        event2 = scheduler(**event_data[1])
        scheduler.can_schedule(event2)
        scheduler.save(event2)

        self.assertEqual(event1.eta, 106)
        self.assertEqual(event1.get_start(), 106)
        self.assertEqual(event1.get_finish(), 119)
        self.assertEqual(event1.duration, 13)

        self.assertEqual(event2.eta, 127)
        self.assertEqual(event2.get_start(), 127)
        self.assertEqual(event2.get_finish(), 138)
        self.assertEqual(event2.duration, 11)

    def test_schedule_independent_ordering(self):
        event_data = [
            {'eta': 0, 'duration': 5, 'callback': None},
            {'eta': 3, 'duration': 3, 'callback': None},
            {'eta': 3, 'duration': 5, 'callback': None},
            {'eta': 8, 'duration': 2, 'callback': None},
        ]
        for i, data in enumerate(permutations(event_data)):
            with self.subTest("permutation", i=i, data=data):
                scheduler = BufferScheduler(agent="simulation", horizon=20, buffer_input=2)
                events = []
                for kwargs in data:
                    event = scheduler(**kwargs)
                    self.assertTrue(scheduler.can_schedule(event))
                    self.assertTrue(scheduler.save(event))
                    events.append(event)

                # sort events (and validate sorting)
                events = sorted(events)
                for j in range(1, len(events)):
                    self.assertTrue(events[j - 1] < events[j])

                if i == 0:
                    ref = events
                    self.assertEqual(events[0].eta, 0)
                    self.assertEqual(events[0].get_start(), 0)
                    self.assertEqual(events[0].get_finish(), 5)
                    self.assertEqual(events[0].etd, 5)
                    self.assertEqual(events[1].eta, 3)
                    self.assertEqual(events[1].get_start(), 5)
                    self.assertEqual(events[1].get_finish(), 8)
                    self.assertEqual(events[1].etd, 8)
                    self.assertEqual(events[2].eta, 3)
                    self.assertEqual(events[2].get_start(), 8)
                    self.assertEqual(events[2].get_finish(), 13)
                    self.assertEqual(events[2].etd, 13)
                    self.assertEqual(events[3].eta, 8)
                    self.assertEqual(events[3].get_start(), 13)
                    self.assertEqual(events[3].get_finish(), 15)
                    self.assertEqual(events[3].etd, 15)
                else:
                    for j, event in enumerate(events):
                        self.assertEqual(event.eta, ref[j].eta)
                        self.assertEqual(event.get_start(), ref[j].get_start())
                        self.assertEqual(event.get_finish(), ref[j].get_finish())
                        self.assertEqual(event.etd, ref[j].etd)

    def test_schedule_until_full(self):
        scheduler = BufferScheduler(agent="simulation", horizon=20, buffer_input=2)

        event1 = scheduler(eta=0, duration=1, callback=None)
        result = scheduler.save(event1)
        self.assertTrue(result)

        event2 = scheduler(eta=0, duration=2, callback=None)
        result = scheduler.save(event2)
        self.assertTrue(result)

        event3 = scheduler(eta=0, duration=3, callback=None)
        result = scheduler.save(event3)
        self.assertTrue(result)

        event4 = scheduler(eta=0, duration=4, callback=None)
        result = scheduler.save(event4)
        self.assertFalse(result)

        self.assertEqual(len(scheduler), 3)
        self.assertEqual(event1.get_start(), 0)
        self.assertEqual(event2.get_start(), 1)
        self.assertEqual(event3.get_start(), 3)

        self.assertEqual(event1.get_finish(), 1)
        self.assertEqual(event2.get_finish(), 3)
        self.assertEqual(event3.get_finish(), 6)

    def test_schedule_overlap_started(self):
        scheduler = BufferScheduler(agent="simulation", horizon=20, buffer_input=2)

        event1 = scheduler(eta=0, duration=3, callback=None)
        event1.start(0)
        result = scheduler.save(event1)
        self.assertTrue(result)

        event2 = scheduler(eta=0, duration=2, callback=None)
        result = scheduler.save(event2)
        self.assertTrue(result)

        event3 = scheduler(eta=0, duration=3, callback=None)
        result = scheduler.save(event3)
        self.assertTrue(result)

        event4 = scheduler(eta=0, duration=4, callback=None)
        result = scheduler.save(event4)
        self.assertFalse(result)

        self.assertEqual(len(scheduler), 3)
        self.assertEqual(event1.get_start(), 0)
        self.assertEqual(event2.get_start(), 3)
        self.assertEqual(event3.get_start(), 5)

        self.assertEqual(event1.get_finish(), 3)
        self.assertEqual(event2.get_finish(), 5)
        self.assertEqual(event3.get_finish(), 8)

    def test_failed_in_simulation1(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5, buffer_input=1)
        event1 = scheduler(eta=0, duration=1, callback=None)
        event1.arrive(0)
        result = scheduler.save(event1)
        self.assertTrue(result)
        event2 = scheduler(eta=1, duration=1, callback=None)
        result = scheduler.save(event2)
        self.assertTrue(result)

    def test_failed_in_simulation2(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5, buffer_input=1)
        event1 = scheduler(eta=0, duration=1, callback=None)
        self.assertTrue(scheduler.save(event1))
        self.assertTrue(scheduler.validate())
        event1.start(1)
        self.assertTrue(scheduler.validate(), "scheduler is invalid after start")

    def test_failed_in_simulation3(self):
        scheduler = BufferScheduler(agent="simulation", horizon=50000, buffer_input=2)

        event1 = scheduler(eta=911068, duration=998, callback=None)
        event1.start(912382)
        self.assertTrue(scheduler.save(event1))
        self.assertTrue(scheduler.validate())

        event2 = scheduler(eta=911461, duration=1026, callback=None)
        event2.arrive(911461)
        self.assertTrue(scheduler.save(event2))
        self.assertTrue(scheduler.validate())

        event3 = scheduler(eta=915810, duration=830, callback=None)
        self.assertTrue(scheduler.save(event3))
        self.assertTrue(scheduler.validate())

        event4 = scheduler(eta=917534, duration=1042, callback=None)
        self.assertTrue(scheduler.save(event4))
        self.assertTrue(scheduler.validate())

    def test_iteration(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5, buffer_input=1)
        event1 = scheduler(eta=0, duration=1, callback=None)
        self.assertTrue(self.scheduler.save(event1))
        event2 = scheduler(eta=1, duration=1, callback=None)
        self.assertTrue(self.scheduler.save(event2))

        events = list(self.scheduler.get_events(None))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], event1)
        self.assertEqual(events[1], event2)

    def test_event_started(self):
        scheduler = BufferScheduler(agent="simulation", horizon=25)
        event1 = self.scheduler(eta=9, etd=11, duration=2, callback=None)
        self.assertTrue(scheduler.save(event1))
        self.assertEqual(event1.state, SchedulerState.SCHEDULED)

        event2 = self.scheduler(eta=19, etd=21, duration=2, callback=None)
        self.assertTrue(scheduler.save(event2))
        self.assertEqual(event2.state, SchedulerState.SCHEDULED)

        event1.arrive(8)
        event1.start(9)

        event3 = self.scheduler(eta=(9, 10), duration=2, callback=None)
        self.assertTrue(scheduler.save(event3))

        self.assertEqual(event3.eta, 9)
        self.assertEqual(event3.get_start(), 11)
        self.assertEqual(event3.get_finish(), 13)
        self.assertEqual(event3.etd, 13)

    def test_event_finished(self):
        scheduler = BufferScheduler(agent="simulation", horizon=15)
        event1 = self.scheduler(eta=4, etd=6, duration=2, callback=None)
        self.assertTrue(scheduler.save(event1))
        self.assertEqual(event1.state, SchedulerState.SCHEDULED)

        event1.arrive(3)
        self.assertTrue(scheduler.validate(), "arrive is invalid")

        event1.start(4)
        self.assertTrue(scheduler.validate(), "start is invalid")

        event1.finish(5)
        self.assertTrue(scheduler.validate(), "finish is invalid")

        event2 = self.scheduler(eta=(4, 5), duration=2, callback=None)
        self.assertTrue(scheduler.save(event2))

        self.assertEqual(event2.eta, 4)
        self.assertEqual(event2.get_start(), 4)
        self.assertEqual(event2.get_finish(), 6)
        self.assertEqual(event2.etd, 6)

    def test_event_negative_eta(self):
        event = self.scheduler(eta=-1, duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.eta, -1)
        self.assertEqual(event.get_start(), -1)
        self.assertEqual(event.get_finish(), 1)
        self.assertEqual(event.etd, 1)
        self.assertEqual(event.duration, 2)
