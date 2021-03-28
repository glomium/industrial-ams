#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.scheduler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,too-many-public-methods  # noqa

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

    def setUp(self):
        self.scheduler = BufferScheduler(agent="simulation", horizon=30, resolution=0.5)

    def test_repr(self):
        self.assertEqual(
            repr(self.scheduler),
            "<BufferScheduler(horizon=(60 * 0.5), buffer_input=[1], buffer_output=[1])>",
        )

    def test_event_to_long(self):
        event = self.scheduler(eta=0, etd=1, duration=2, callback=None)
        with self.assertRaises(CanNotSchedule):
            self.scheduler.can_schedule(event)

    def test_schedule_one_single_eta(self):
        event = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event)
        self.assertTrue(result)

        self.assertEqual(event.get_eta(), 0.0)
        self.assertEqual(event.get_start(), 0.0)
        self.assertEqual(event.get_finish(), 2.0)
        self.assertEqual(event.get_etd(), 2.0)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), None)
        self.assertEqual(event.get_eta_max(), None)
        self.assertEqual(event.get_etd_min(), 2.0)
        self.assertEqual(event.get_etd_max(), None)

    def test_schedule_one_ranged_eta(self):
        event = self.scheduler(eta=[0, 5], duration=2, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 0.0)
        self.assertEqual(event.get_start(), 5.0)
        self.assertEqual(event.get_finish(), 7.0)
        self.assertEqual(event.get_etd(), 7.0)
        self.assertEqual(event.duration, 2)
        self.assertEqual(event.get_eta_min(), 0)
        self.assertEqual(event.get_eta_max(), 5)
        self.assertEqual(event.get_etd_min(), 7.0)
        self.assertEqual(event.get_etd_max(), None)

    def test_schedule_until_full(self):
        self.scheduler = BufferScheduler(agent="simulation", horizon=30, resolution=0.5, buffer_input=2)
        event1 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event1)
        self.assertTrue(result)

        self.assertEqual(event1.get_eta(), 0.0)
        self.assertEqual(event1.get_start(), 0.0)
        self.assertEqual(event1.get_finish(), 2.0)
        self.assertEqual(event1.get_etd(), 2.0)
        self.assertEqual(event1.duration, 2)
        self.assertEqual(event1.get_eta_min(), None)
        self.assertEqual(event1.get_eta_max(), None)
        self.assertEqual(event1.get_etd_min(), 2.0)
        self.assertEqual(event1.get_etd_max(), None)

        event2 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event2)
        self.assertTrue(result)

        self.assertEqual(event2.get_eta(), 0.0)
        self.assertEqual(event2.get_start(), 2.0)
        self.assertEqual(event2.get_finish(), 4.0)
        self.assertEqual(event2.get_etd(), 4.0)
        self.assertEqual(event2.duration, 2)

        self.assertEqual(event2.get_eta_min(), 0)
        self.assertEqual(event2.get_eta_max(), None)
        self.assertEqual(event2.get_etd_min(), 4.0)
        self.assertEqual(event2.get_etd_max(), None)

        self.assertEqual(event1.get_eta_min(), None)
        self.assertEqual(event1.get_eta_max(), 0)
        self.assertEqual(event1.get_etd_min(), 2.0)
        self.assertEqual(event1.get_etd_max(), 4.0)

        event3 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event3)
        self.assertTrue(result)

        self.assertEqual(event3.get_eta(), 0.0)
        self.assertEqual(event3.get_start(), 4.0)
        self.assertEqual(event3.get_finish(), 6.0)
        self.assertEqual(event3.get_etd(), 6.0)
        self.assertEqual(event3.duration, 2)

        self.assertEqual(event3.get_eta_min(), 0)
        self.assertEqual(event3.get_eta_max(), None)
        self.assertEqual(event3.get_etd_min(), 6.0)
        self.assertEqual(event3.get_etd_max(), None)

        self.assertEqual(event2.get_eta_min(), 0)
        self.assertEqual(event2.get_eta_max(), 0)
        self.assertEqual(event2.get_etd_min(), 4.0)
        self.assertEqual(event2.get_etd_max(), 6.0)

        event4 = self.scheduler(eta=0, duration=2, callback=None)
        result = self.scheduler.save(event4)
        self.assertFalse(result)

    def setup1(self):
        # pylint: disable=attribute-defined-outside-init
        self.event1 = self.scheduler(eta=(9, 9, 9), etd=(11, 11, 11), duration=2, callback=None)
        self.scheduler.save(self.event1)
        self.event2 = self.scheduler(eta=(19, 19, 19), etd=(21, 21, 21), duration=2, callback=None)
        self.scheduler.save(self.event2)

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
        self.assertEqual(event.get_eta(), 3.0)
        self.assertEqual(event.get_start(), 3.0)
        self.assertEqual(event.get_finish(), 6.0)
        self.assertEqual(event.get_etd(), 6.0)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 0)
        self.assertEqual(event.get_eta_max(), 3)
        self.assertEqual(event.get_etd_min(), 6.0)
        self.assertEqual(event.get_etd_max(), 11.0)

    def test_new_event_middle(self):
        self.setup1()
        event = self.scheduler(eta=(10, 13), duration=3, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 13.0)
        self.assertEqual(event.get_start(), 13.0)
        self.assertEqual(event.get_finish(), 16.0)
        self.assertEqual(event.get_etd(), 16.0)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 10)
        self.assertEqual(event.get_eta_max(), 13)
        self.assertEqual(event.get_etd_min(), 16.0)
        self.assertEqual(event.get_etd_max(), 21.0)

    def test_new_event_end(self):
        self.setup1()
        event = self.scheduler(eta=(20, 23), duration=3, callback=None)
        result = self.scheduler.save(event)

        self.assertTrue(result)
        self.assertEqual(event.get_eta(), 23.0)
        self.assertEqual(event.get_start(), 23.0)
        self.assertEqual(event.get_finish(), 26.0)
        self.assertEqual(event.get_etd(), 26.0)
        self.assertEqual(event.duration, 3)
        self.assertEqual(event.get_eta_min(), 20)
        self.assertEqual(event.get_eta_max(), 23)
        self.assertEqual(event.get_etd_min(), 26.0)
        self.assertEqual(event.get_etd_max(), None)

#   @unittest.expectedFailure
#   def test_event_eta1(self):
#       event = self.scheduler(eta=2, duration=1, callback=None)
#       result = [
#           2, 2, 2,  # eta
#           3, None, 50,  # etd
#           2, 50, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_eta2(self):
#       event = self.scheduler(eta=(1, 3), duration=1, callback=None)
#       result = [
#           1, None, 3,  # eta
#           2, None, 50,  # etd
#           1, 50, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_eta3(self):
#       event = self.scheduler(eta=(1, 2, 3), duration=1, callback=None)
#       result = [
#           1, 2, 3,  # eta
#           3, None, 50,  # etd
#           2, 50, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_etd1(self):
#       event = self.scheduler(etd=3, duration=1, callback=None)
#       result = [
#           0, None, 2,  # eta
#           3, 3, 3,  # etd
#           0, 3, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_etd2(self):
#       event = self.scheduler(etd=(2, 4), duration=1, callback=None)
#       result = [
#           0, None, 3,  # eta
#           2, None, 4,  # etd
#           0, 4, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_etd3(self):
#       event = self.scheduler(etd=(2, 3, 4), duration=1, callback=None)
#       result = [
#           0, None, 2,  # eta
#           2, 3, 4,  # etd
#           0, 3, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_arrived(self):
#       event = self.scheduler(etd=4, duration=1, callback=None)
#       event.arrive(1)
#       result = [
#           1, 1, 1,  # eta
#           4, 4, 4,  # etd
#           1, 4, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_arrived_canceled(self):
#       event = self.scheduler(etd=4, duration=1, callback=None)
#       event.arrive(1)
#       event.cancel()
#       result = [
#           1, 1, 1,  # eta
#           4, 4, 4,  # etd
#           1, 4, True,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_started(self):
#       event = self.scheduler(etd=4, duration=1, callback=None)
#       event.arrive(1)
#       event.start(2)
#       result = [
#           None, None, None,  # eta
#           4, 4, 4,  # etd
#           2, 3, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_finished(self):
#       event = self.scheduler(etd=4, duration=1, callback=None)
#       event.arrive(1)
#       event.start(2)
#       event.finish(3)
#       result = [
#           None, None, None,  # eta
#           4, 4, 4,  # etd
#           None, 3, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_finished_max(self):
#       event = self.scheduler(etd=(2, 5), duration=1, callback=None)
#       event.arrive(1)
#       event.start(2)
#       event.finish(3)
#       result = [
#           None, None, None,  # eta
#           3, None, 5,  # etd
#           None, 3, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, 0, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_negative_eta(self):
#       event = self.scheduler(eta=-1, etd=(2, 5), duration=1, callback=None)
#       result = [
#           -1, -1, -1,  # eta
#           2, None, 5,  # etd
#           -1, 5, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, -1, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_negative_etd(self):
#       event = self.scheduler(etd=(-2, 5), duration=1, callback=None)
#       result = [
#           0, None, 4,  # eta
#           -2, None, 5,  # etd
#           0, 5, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, -2, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
#
#   @unittest.expectedFailure
#   def test_event_negative_arrived(self):
#       event = self.scheduler(etd=(2, 5), duration=1, callback=None)
#       event.arrive(-1)
#       result = [
#           -1, -1, -1,  # eta
#           2, None, 5,  # etd
#           -1, 5, False,  # production
#           1,
#       ]
#       data, offset = self.scheduler.get_event_variables(event)
#       self.assertEqual(data[event]["number"], 1)
#       self.assertEqual(data[event]["il"], None)
#       self.assertEqual(data[event]["ol"], None)
#       self.assertEqual(data[event]["production"], result)
#       self.assertEqual(offset, -1, "offset")
#
#       model, events = self.scheduler.build_model(data, offset)
#       response = self.scheduler.optimize_model(model, events)
#       self.assertEqual(response, None)
