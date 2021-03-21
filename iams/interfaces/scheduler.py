#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from enum import Enum
from enum import auto
from typing import Union

from iams.exceptions import CanNotSchedule


logger = logging.getLogger(__name__)


class States(Enum):
    NEW = auto()
    SCHEDULED = auto()
    ARRIVED = auto()
    STARTED = auto()
    FINISHED = auto()
    DEPARTED = auto()
    CANCELED = auto()


@dataclass
class Event:
    duration: Union[int, float]
    callback: str
    args: Union[list, tuple] = field(default_factory=list, repr=False, init=True, compare=True)
    kwargs: dict = field(default_factory=dict, repr=False, init=True, compare=True)

    state: States = field(default=States.NEW, repr=True, init=True, compare=False)
    schedule_start: Union[float, datetime] = field(default=None, repr=True, init=False, compare=False)
    schedule_finish: Union[float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta: Union[float, datetime] = field(default=None, repr=True, init=True, compare=True)
    eta_min: Union[float, datetime] = field(default=None, repr=True, init=True, compare=False)
    eta_max: Union[float, datetime] = field(default=None, repr=True, init=True, compare=False)
    etd: Union[float, datetime] = field(default=None, repr=True, init=True, compare=True)
    etd_min: Union[float, datetime] = field(default=None, repr=True, init=True, compare=False)
    etd_max: Union[float, datetime] = field(default=None, repr=True, init=True, compare=False)
    use_datetime: bool = field(default=False, repr=False, init=False, compare=False)

    def __post_init__(self):
        if isinstance(self.eta, datetime):
            self.use_datetime = True

    def _get_time(self, name, now):
        value = getattr(self, name)
        if isinstance(value, datetime):
            assert isinstance(now, datetime), "When using datetime, the current time needs to be provided"
            assert self.use_datetime, "Model does not use datetime"
            return (value - now).total_seconds()
        return value

    def _set_time(self, name, seconds, now):
        if self.use_datetime:
            assert isinstance(now, datetime), "When using datetime, the current time needs to be provided"
            setattr(self, name, now + timedelta(seconds=seconds))
        else:
            setattr(self, name, seconds)

    def arrive(self):
        self.state = States.ARRIVED

    def cancel(self):
        self.state = States.CANCELED

    def depart(self):
        self.state = States.DEPARTED

    def finish(self):
        self.state = States.FINISHED

    def schedule(self):
        self.state = States.SCHEDULED

    def start(self):
        self.state = States.STARTED

    def get_duration(self):
        return self.duration

    def get_start(self, now=None):
        return self._get_time("schedule_start", now)

    def get_finish(self, now=None):
        return self._get_time("schedule_finish", now)

    def get_eta(self, now=None):
        return self._get_time("eta", now)

    def get_eta_max(self, now=None):
        return self._get_time("eta_max", now)

    def get_eta_min(self, now=None):
        return self._get_time("eta_min", now)

    def get_etd(self, now=None):
        return self._get_time("etd", now)

    def get_etd_max(self, now=None):
        return self._get_time("etd_max", now)

    def get_etd_min(self, now=None):
        return self._get_time("etd_min", now)

    def set_start(self, seconds, now=None):
        return self._set_time("schedule_start", seconds, now)

    def set_finish(self, seconds, now=None):
        return self._set_time("schedule_finish", seconds, now)

    def set_eta(self, seconds, now=None):
        return self._set_time("eta", seconds, now)

    def set_eta_max(self, seconds, now=None):
        return self._set_time("eta_max", seconds, now)

    def set_eta_min(self, seconds, now=None):
        return self._set_time("eta_min", seconds, now)

    def set_etd(self, seconds, now=None):
        return self._set_time("etd", seconds, now)

    def set_etd_max(self, seconds, now=None):
        return self._set_time("etd_max", seconds, now)

    def set_etd_min(self, seconds, now=None):
        return self._set_time("etd_min", seconds, now)


class SchedulerInterface(ABC):

    def __init__(self, agent):
        self._agent = agent
        self.events = []

    def __call__(self, **kwargs):
        """
        """
        return Event(**kwargs)

    @abstractmethod
    def schedule(self, event):  # pragma: no cover
        """
        """
        pass

    @abstractmethod
    def can_schedule(self, event):  # pragma: no cover
        """
        Returns True if an event can be scheduled
        """
        pass

    def add(self, event, now=None):  # pragma: no cover
        try:
            response = self.schedule(event, now)
        except CanNotSchedule:
            return False

        if response is None or response is True:
            self.events.append(event)
            return True
        return False

    def cancel(self, event):
        """
        """
        response = False
        for i, e in enumerate(self.events):
            if e == event:
                del self.events[i]
                response = True
                break
        return response
