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
        scheduler = BufferScheduler(agent="simulation", horizon=5)
        self.assertEqual(
            repr(scheduler),
            "<BufferScheduler(horizon=5, buffer_input=[1], buffer_output=[1], production_lines=1, resolution=1.0)>",
        )

    def test_event_okay(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5)
        event = scheduler(eta=0, etd=1, duration=1, callback=None)
        result = scheduler.can_schedule(event)
        self.assertTrue(result)

    def test_event_to_long(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5)
        event = scheduler(eta=0, etd=1, duration=2, callback=None)
        with self.assertRaises(CanNotSchedule):
            scheduler.can_schedule(event)

    def test_two_events(self):
        scheduler = BufferScheduler(agent="simulation", horizon=5)
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
        scheduler = BufferScheduler(agent="simulation", horizon=5)
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
        scheduler = BufferScheduler(agent="simulation", horizon=5)
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
        scheduler = BufferScheduler(agent="simulation", horizon=5)
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


@unittest.skipIf(SKIP is not None, SKIP)
class BufferSchedulerEventVariablesTests(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.scheduler = BufferScheduler(agent="simulation", horizon=50)

    def test_event_none(self):
        event = self.scheduler(duration=1, callback=None)
        result = {
            ('eta', 0): None,
            ('etd', 0): None,
            ('il', 0): None,
            ('iq', 0): (0, 49),
            ('ol', 0): None,
            ('oq', 0): (1, 50),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_eta1(self):
        event = self.scheduler(eta=2, duration=1, callback=None)
        result = {
            ('eta', 0): 2,
            ('etd', 0): None,
            ('il', 0): None,
            ('iq', 0): (2, 2),
            ('ol', 0): None,
            ('oq', 0): (3, 50),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_eta2(self):
        event = self.scheduler(eta=(1, 3), duration=1, callback=None)
        result = {
            ('eta', 0): None,
            ('etd', 0): None,
            ('il', 0): None,
            ('iq', 0): (1, 3),
            ('ol', 0): None,
            ('oq', 0): (2, 50),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_eta3(self):
        event = self.scheduler(eta=(1, 2, 3), duration=1, callback=None)
        result = {
            ('eta', 0): 2,
            ('etd', 0): None,
            ('il', 0): None,
            ('iq', 0): (1, 3),
            ('ol', 0): None,
            ('oq', 0): (2, 50),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_etd1(self):
        event = self.scheduler(etd=3, duration=1, callback=None)
        result = {
            ('eta', 0): None,
            ('etd', 0): 3,
            ('il', 0): None,
            ('iq', 0): (0, 2),
            ('ol', 0): None,
            ('oq', 0): (3, 3),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_etd2(self):
        event = self.scheduler(etd=(2, 4), duration=1, callback=None)
        result = {
            ('eta', 0): None,
            ('etd', 0): None,
            ('il', 0): None,
            ('iq', 0): (0, 3),
            ('ol', 0): None,
            ('oq', 0): (2, 4),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_etd3(self):
        event = self.scheduler(etd=(2, 3, 4), duration=1, callback=None)
        result = {
            ('eta', 0): None,
            ('etd', 0): 3,
            ('il', 0): None,
            ('iq', 0): (0, 3),
            ('ol', 0): None,
            ('oq', 0): (2, 4),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_arrived(self):
        event = self.scheduler(etd=4, duration=1, callback=None)
        event.arrive(1)
        result = {
            ('eta', 0): 1,
            ('etd', 0): 4,
            ('il', 0): None,
            ('ol', 0): None,
            ('oq', 0): (4, 4),
            ('p', 0): (None, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_arrived_canceled(self):
        event = self.scheduler(etd=4, duration=1, callback=None)
        event.arrive(1)
        event.cancel()
        result = {
            ('eta', 0): 1,
            ('etd', 0): 4,
            ('il', 0): None,
            ('ol', 0): None,
            ('oq', 0): (4, 4),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_started(self):
        event = self.scheduler(etd=4, duration=1, callback=None)
        event.arrive(1)
        event.start(2)
        result = {
            ('etd', 0): 4,
            ('ol', 0): None,
            ('oq', 0): (3, 4),
            ('p', 0): (2, 1),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_finished(self):
        event = self.scheduler(etd=4, duration=1, callback=None)
        event.arrive(1)
        event.start(2)
        event.finish(3)
        result = {
            ('etd', 0): 4,
            ('ol', 0): None,
            ('oq', 0): (3, 4),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")

    def test_event_finished_max(self):
        event = self.scheduler(etd=(2, 5), duration=1, callback=None)
        event.arrive(1)
        event.start(2)
        event.finish(3)
        result = {
            ('etd', 0): None,
            ('ol', 0): None,
            ('oq', 0): (3, 5),
        }
        data, offset = self.scheduler.get_event_variables(event)
        self.assertEqual(data[event], result)
        self.assertEqual(offset, 0, "offset")
