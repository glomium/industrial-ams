#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.scheduler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,too-many-public-methods  # noqa

from itertools import permutations
from operator import attrgetter
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
        event = self.scheduler(eta=0, duration=1, callback=None)

        with self.subTest("new"):
            self.scheduler.can_schedule(event)
            self.assertEqual(event.state, SchedulerState.NEW)
            self.assertEqual(event.get_eta(), 0)

        with self.subTest("scheduled"):
            event.schedule([1, 1])
            self.scheduler.can_schedule(event)
            self.assertEqual(event.state, SchedulerState.SCHEDULED)
            self.assertEqual(event.get_etd(), 1)

        with self.subTest("arrive"):
            event.arrive(0)
            self.scheduler.can_schedule(event)
            self.assertEqual(event.state, SchedulerState.ARRIVED)

        with self.subTest("start"):
            event.start(0)
            self.scheduler.can_schedule(event)
            self.assertEqual(event.state, SchedulerState.STARTED)

        with self.subTest("finish"):
            event.finish(1)
            self.scheduler.can_schedule(event)
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

        self.assertEqual(event.get_eta(), 0)
        self.assertEqual(event.get_start(), 0)
        self.assertEqual(event.get_finish(), 2)
        self.assertEqual(event.get_etd(), 2)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), None)
        self.assertEqual(event.get_eta_max(), None)
        self.assertEqual(event.get_etd_min(), 2)
        self.assertEqual(event.get_etd_max(), None)

    def test_schedule_one_ranged_eta(self):
        event = self.scheduler(eta=[0, 5], duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 0, "ETA")
        self.assertEqual(event.get_start(), 5, "Start")
        self.assertEqual(event.get_finish(), 7, "Finish")
        self.assertEqual(event.get_etd(), 7, "ETD")
        self.assertEqual(event.duration, 2, "Duration")
        self.assertEqual(event.get_eta_min(), 0, "ETA-low")
        self.assertEqual(event.get_eta_max(), 5, "ETA-high")
        self.assertEqual(event.get_etd_min(), 7, "ETD-low")
        self.assertEqual(event.get_etd_max(), None, "ETD-high")

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

        self.assertEqual(event1.get_eta(), 106)
        self.assertEqual(event1.get_start(), 106)
        self.assertEqual(event1.get_finish(), 119)
        self.assertEqual(event1.get_etd_min(), 119)
        self.assertEqual(event1.duration, 13)

        self.assertEqual(event2.get_eta(), 127)
        self.assertEqual(event2.get_start(), 127)
        self.assertEqual(event2.get_finish(), 138)
        self.assertEqual(event2.get_etd_min(), 138)
        self.assertEqual(event2.duration, 11)

    def test_schedule_independent_ordering(self):
        event_data = [
            {'eta': (7, 7, 7), 'duration': 12, 'callback': None},
            {'eta': (18, 18, 18), 'duration': 7, 'callback': None},
            {'eta': (30, 30, 30), 'duration': 12, 'callback': None},
            {'eta': (27, 27, 27), 'duration': 9, 'callback': None},
        ]
        for i, data in enumerate(permutations(event_data)):
            with self.subTest("permutation", i=i, data=data):
                scheduler = BufferScheduler(agent="simulation", horizon=60, buffer_input=1)
                events = []
                for kwargs in data:
                    event = scheduler(**kwargs)
                    scheduler.can_schedule(event)
                    scheduler.save(event)
                    events.append(event)
                events = list(sorted(events, key=attrgetter('eta')))
                if i == 0:
                    reference = events
                else:
                    for j, event in enumerate(events):
                        self.assertEqual(event.get_eta(), reference[j].get_eta())
                        self.assertEqual(event.get_start(), reference[j].get_start())
                        self.assertEqual(event.get_finish(), reference[j].get_finish())
                        self.assertEqual(event.get_etd(), reference[j].get_etd())

    def test_schedule_until_full(self):
        self.scheduler = BufferScheduler(agent="simulation", horizon=30, buffer_input=2)
        event1 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event1)
        self.assertTrue(result)

        self.assertEqual(event1.get_eta(), 0)
        self.assertEqual(event1.get_start(), 0)
        self.assertEqual(event1.get_finish(), 2)
        self.assertEqual(event1.get_etd(), 2)
        self.assertEqual(event1.duration, 2)
        self.assertEqual(event1.get_eta_min(), None)
        self.assertEqual(event1.get_eta_max(), None)
        self.assertEqual(event1.get_etd_min(), 2)
        self.assertEqual(event1.get_etd_max(), None)
        event1.schedule([2, 2])

        event2 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event2)
        self.assertTrue(result)

        self.assertEqual(event2.get_eta(), 0)
        self.assertEqual(event2.get_start(), 2)
        self.assertEqual(event2.get_finish(), 4)
        self.assertEqual(event2.get_etd(), 4)
        self.assertEqual(event2.duration, 2)

        self.assertEqual(event2.get_eta_min(), 0)
        self.assertEqual(event2.get_eta_max(), None)
        self.assertEqual(event2.get_etd_min(), 4)
        self.assertEqual(event2.get_etd_max(), None)
        event2.schedule([4, 4])

        event3 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event3)
        self.assertTrue(result)

        self.assertEqual(event3.get_eta(), 0)
        self.assertEqual(event3.get_start(), 4)
        self.assertEqual(event3.get_finish(), 6)
        self.assertEqual(event3.get_etd(), 6)
        self.assertEqual(event3.duration, 2)

        self.assertEqual(event3.get_eta_min(), 0)
        self.assertEqual(event3.get_eta_max(), None)
        self.assertEqual(event3.get_etd_min(), 6)
        self.assertEqual(event3.get_etd_max(), None)
        event2.schedule([6, 6])

        event4 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event4)
        self.assertFalse(result)

    def setup1(self):
        # pylint: disable=attribute-defined-outside-init
        self.event1 = self.scheduler(eta=(9, 9, 9), etd=(11, 11, 11), duration=2, callback=None)
        self.scheduler.save(self.event1)
        self.event2 = self.scheduler(eta=(19, 19, 19), etd=(21, 21, 21), duration=2, callback=None)
        self.scheduler.save(self.event2)
        self.assertEqual(self.event1.state, SchedulerState.SCHEDULED)
        self.assertEqual(self.event2.state, SchedulerState.SCHEDULED)

    def test_iteration(self):
        self.setup1()
        events = list(self.scheduler.get_events(None))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], self.event1)
        self.assertEqual(events[1], self.event2)

    def test_values_event1(self):
        self.setup1()
        self.assertEqual(self.event1.get_eta(), 9)
        self.assertEqual(self.event1.get_eta_min(), 9)
        self.assertEqual(self.event1.get_eta_max(), 9)
        self.assertEqual(self.event1.get_start(), 9)
        self.assertEqual(self.event1.get_finish(), 11)
        self.assertEqual(self.event1.get_etd(), 11)
        self.assertEqual(self.event1.get_etd_min(), 11)
        self.assertEqual(self.event1.get_etd_max(), 11)
        self.assertEqual(self.event1.duration, 2)

    def test_values_event2(self):
        self.setup1()
        self.assertEqual(self.event2.get_eta(), 19)
        self.assertEqual(self.event2.get_eta_min(), 19)
        self.assertEqual(self.event2.get_eta_max(), 19)
        self.assertEqual(self.event2.get_start(), 19)
        self.assertEqual(self.event2.get_finish(), 21)
        self.assertEqual(self.event2.get_etd(), 21)
        self.assertEqual(self.event2.get_etd_min(), 21)
        self.assertEqual(self.event2.get_etd_max(), 21)
        self.assertEqual(self.event2.duration, 2)

    def test_new_event_begin(self):
        self.setup1()
        event = self.scheduler(eta=(0, 3), duration=3, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 0)
        self.assertEqual(event.get_start(), 3)
        self.assertEqual(event.get_finish(), 6)
        self.assertEqual(event.get_etd(), 6)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 0)
        self.assertEqual(event.get_eta_max(), 3)
        self.assertEqual(event.get_etd_min(), 6)
        self.assertEqual(event.get_etd_max(), 11)

    def test_new_event_middle(self):
        self.setup1()
        event = self.scheduler(eta=(10, 13), duration=3, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 10)
        self.assertEqual(event.get_start(), 13)
        self.assertEqual(event.get_finish(), 16)
        self.assertEqual(event.get_etd(), 16)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 10)
        self.assertEqual(event.get_eta_max(), 13)
        self.assertEqual(event.get_etd_min(), 16)
        self.assertEqual(event.get_etd_max(), 21)

    def test_new_event_end(self):
        self.setup1()
        event = self.scheduler(eta=(20, 23), duration=3, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 20)
        self.assertEqual(event.get_start(), 23)
        self.assertEqual(event.get_finish(), 26)
        self.assertEqual(event.get_etd(), 26)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 20)
        self.assertEqual(event.get_eta_max(), 23)
        self.assertEqual(event.get_etd_min(), 26)
        self.assertEqual(event.get_etd_max(), None)

    def test_event_arrived(self):
        self.setup1()
        self.event1.arrive(8)
        event = self.scheduler(eta=(9, 10), duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 9)
        self.assertEqual(event.get_start(), 10)
        self.assertEqual(event.get_finish(), 12)
        self.assertEqual(event.get_etd(), 12)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), 9)
        self.assertEqual(event.get_eta_max(), 10)
        self.assertEqual(event.get_etd_min(), 12)
        self.assertEqual(event.get_etd_max(), 21)

    def test_event_arrived_canceled(self):
        self.setup1()
        self.event1.arrive(8)
        self.event1.cancel()
        event = self.scheduler(eta=(9, 10), duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 9)
        self.assertEqual(event.get_start(), 10)
        self.assertEqual(event.get_finish(), 12)
        self.assertEqual(event.get_etd(), 12)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), 9)
        self.assertEqual(event.get_eta_max(), 10)
        self.assertEqual(event.get_etd_min(), 12)
        self.assertEqual(event.get_etd_max(), 21)

    def test_event_started(self):
        self.setup1()
        self.event1.arrive(8)
        self.event1.start(9)
        event = self.scheduler(eta=(9, 10), duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 9)
        self.assertEqual(event.get_start(), 11)
        self.assertEqual(event.get_finish(), 13)
        self.assertEqual(event.get_etd(), 13)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), 9)
        self.assertEqual(event.get_eta_max(), 10)
        self.assertEqual(event.get_etd_min(), 13)
        self.assertEqual(event.get_etd_max(), 21)

    def test_event_finished(self):
        self.setup1()
        self.event1.arrive(8)
        self.event1.start(9)
        self.event1.finish(10)
        event = self.scheduler(eta=(9, 10), duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 9)
        self.assertEqual(event.get_start(), 10)
        self.assertEqual(event.get_finish(), 12)
        self.assertEqual(event.get_etd(), 12)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), 9)
        self.assertEqual(event.get_eta_max(), 10)
        self.assertEqual(event.get_etd_min(), 12)
        self.assertEqual(event.get_etd_max(), 21)

    def test_event_negative_eta(self):
        event = self.scheduler(eta=-1, duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), -1)
        self.assertEqual(event.get_start(), -1)
        self.assertEqual(event.get_finish(), 1)
        self.assertEqual(event.get_etd(), 1)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), None)
        self.assertEqual(event.get_eta_max(), None)
        self.assertEqual(event.get_etd_min(), 1)
        self.assertEqual(event.get_etd_max(), None)
