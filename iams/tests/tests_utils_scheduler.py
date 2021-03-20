#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from iams.exceptions import CanNotSchedule
from iams.utils.scheduler import BufferScheduler


class ImportTests(unittest.TestCase):  # pragma: no cover

    def test_event_okay(self):
        scheduler = BufferScheduler(agent="simulation")
        event = scheduler(eta=0, etd=1, duration=1, instance="event", callback=None)
        result = scheduler.can_schedule(event)
        self.assertFalse(result)

    def test_event_to_long(self):
        scheduler = BufferScheduler(agent="simulation")
        event = scheduler(eta=0, etd=1, duration=2, instance="event", callback=None)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event)

    def test_two_events(self):
        scheduler = BufferScheduler(agent="simulation")
        event1 = scheduler(eta=0, etd=1, duration=1, instance="event1", callback=None)
        event2 = scheduler(eta=0, etd=1, duration=1, instance="event2", callback=None)
        event3 = scheduler(eta=0, etd=2, duration=1, instance="event3", callback=None)
        event4 = scheduler(eta=0, etd=2, duration=1, instance="event3", callback=None)
        scheduler.schedule(event1)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event2)
        scheduler.schedule(event3)
        self.assertEqual(len(scheduler.events), 2)
        self.assertEqual(scheduler.events[0], event1)
        self.assertEqual(scheduler.events[1], event3)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event4)
        self.assertTrue(scheduler.cancel(event1))
        self.assertFalse(scheduler.cancel(event1))
        self.assertEqual(len(scheduler.events), 1)
        self.assertEqual(scheduler.events[0], event3)
