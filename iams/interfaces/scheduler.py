#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging


from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class SchedulerEvent:
    eta: float
    duration: float
    instance: object
    callback: str
    current_time: float = None
    start: float = None
    finish: float = None
    # self.scheduler.append({'order': schedule, 'step': step, 'length': performance, 'time': time})

    # def schedule(self):
    #     pass

    # def scheduled_start(self):
    #     pass


class SchedulerInterface(ABC):
    def __init__(self, agent):
        self._agent = agent
        self.events = []

    def __call__(self, instance, callback, estimated_duration, current_time, eta=0.0):
        """
        Adds a new event to the scheduler
        """
        logger.debug(
            "%s.scheduler(%s, %s, %s)",
            self._agent, estimated_duration, current_time, eta,
        )

        event = SchedulerEvent(
            callback=callback,
            current_time=current_time,
            duration=estimated_duration,
            eta=eta,
            instance=instance,
        )

        response = self.new_event(event)
        if response is None or response is True:
            self.events.append(event)
            return event
        return None

    def close(self, event):
        """
        Closes the event
        """
        for i, e in enumerate(self.events):
            if e == event:
                del self.events[i]
                break
        return True

    # def __next__(self):
    #     raise NotImplementedError

    @abstractmethod
    def new_event(self, event):  # pragma: no cover
        """
        """
        pass

    @abstractmethod
    def can_schedule(self, estimated_duration, current_time, eta=0.0):  # pragma: no cover
        """
        Returns True if an event can be scheduled
        """
        pass

    def finish(self, event):
        """
        """
        return self.close(event)

    def cancel(self, event):
        """
        """
        return self.close(event)
