#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from iams.interfaces.scheduler import SchedulerInterface


logger = logging.getLogger(__name__)


class TestScheduler(SchedulerInterface):

    def can_schedule(self, estimated_duration, current_time, eta=0.0):
        pass

    def new_event(self, event):
        pass
