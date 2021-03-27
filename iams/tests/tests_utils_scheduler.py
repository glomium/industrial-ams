#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.scheduler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

from iams.exceptions import CanNotSchedule

try:
    from iams.utils.scheduler import BufferScheduler
except ImportError as exception:  # pragma: no cover
    SKIP = str(exception)
else:
    SKIP = None


@unittest.skipIf(SKIP is not None, SKIP)
class BufferSchedulerTests(unittest.TestCase):  # pragma: no cover

    def test_repr(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        self.assertEqual(
            repr(scheduler),
            "<BufferScheduler(buffer_input=[1], buffer_output=[1], ceiling=5, production_lines=1, resolution=1.0)>",
        )

    def test_event_okay(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event = scheduler(eta=0, etd=1, duration=1, callback=None)
        result = scheduler.can_schedule(event)
        self.assertTrue(result)

    def test_event_to_long(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event = scheduler(eta=0, etd=1, duration=2, callback=None)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event)

    def test_two_events(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event1 = scheduler(eta=0, etd=1, duration=1, callback=None)
        event2 = scheduler(eta=0, etd=1, duration=1, callback=None)
        event3 = scheduler(eta=0, etd=2, duration=1, callback=None)
        event4 = scheduler(eta=0, etd=2, duration=1, callback=None)
        scheduler.save(event1)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event2)
        scheduler.save(event3)
        self.assertEqual(len(scheduler._events), 2)
        self.assertEqual(scheduler._events[0], event1)
        self.assertEqual(scheduler._events[1], event3)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event4)
        # self.assertTrue(scheduler.cancel(event1))
        # self.assertFalse(scheduler.cancel(event1))
        # self.assertEqual(len(scheduler.events), 1)
        # self.assertEqual(scheduler.events[0], event3)

    @unittest.expectedFailure
    def test_event_no_etd(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event = scheduler(eta=0, duration=1, callback=None)
        scheduler.save(event)
        self.assertEqual(event.get_eta(), 0)
        self.assertEqual(event.get_etd(), 1)
        self.assertEqual(event.get_min_eta(), 0)
        self.assertEqual(event.get_max_eta(), 4)
        self.assertEqual(event.get_min_etd(), 1)
        self.assertEqual(event.get_max_etd(), 5)

    @unittest.expectedFailure
    def test_event_schedule_before(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event1 = scheduler(eta=2, etd=3, duration=1, callback=None)
        event1.schedule()
        scheduler.save(event1)
        event2 = scheduler(eta=0, duration=1, callback=None)
        self.assertEqual(event2.get_eta(), 0)
        self.assertEqual(event2.get_etd(), 1)
        self.assertEqual(event2.get_min_eta(), 0)
        self.assertEqual(event2.get_max_eta(), 2)
        self.assertEqual(event2.get_min_etd(), 1)
        self.assertEqual(event2.get_max_etd(), 3)

    @unittest.expectedFailure
    def test_event_schedule_after(self):
        scheduler = BufferScheduler(agent="simulation", ceiling=5)
        event1 = scheduler(eta=0, etd=3, duration=1, callback=None)
        event1.schedule()
        scheduler.save(event1)
        event2 = scheduler(eta=0, duration=1, callback=None)
        self.assertEqual(event2.get_eta(), 0)
        self.assertEqual(event2.get_etd(), 2)
        self.assertEqual(event2.get_min_eta(), 0)
        self.assertEqual(event2.get_max_eta(), 4)
        self.assertEqual(event2.get_min_etd(), 2)
        self.assertEqual(event2.get_max_etd(), 5)
