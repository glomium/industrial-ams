#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams scheduler interface
"""

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
    """
    Event-states enum
    """
    NEW = auto()
    SCHEDULED = auto()
    ARRIVED = auto()
    STARTED = auto()
    FINISHED = auto()
    DEPARTED = auto()
    CANCELED = auto()


@dataclass
class Event:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """
    Schedule events
    """
    duration: Union[int, float]
    callback: str
    args: Union[list, tuple] = field(default_factory=list, repr=False, init=True, compare=True)
    kwargs: dict = field(default_factory=dict, repr=False, init=True, compare=True)

    state: States = field(default=States.NEW, repr=True, init=True, compare=False)
    schedule_start: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    schedule_finish: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta: Union[list, tuple, int, float, datetime] = field(default=None, repr=True, init=True, compare=True)
    eta_min: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta_max: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    etd: Union[list, tuple, int, float, datetime, None] = field(default=None, repr=True, init=True, compare=True)
    etd_min: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    etd_max: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    use_datetime: bool = field(default=False, repr=False, init=False, compare=False)
    canceled: bool = field(default=False, repr=False, init=False, compare=False)

    def __post_init__(self):  # pylint: disable=too-many-branches
        if isinstance(self.eta, datetime):
            self.use_datetime = True

        if isinstance(self.eta, (tuple, list)):
            if len(self.eta) == 1:
                self.eta = self.eta[0]
            elif len(self.eta) == 2:
                self.eta_min, self.eta_max = self.eta
                self.eta = None
            elif len(self.eta) == 3:
                self.eta_min, self.eta, self.eta_max = self.eta
            else:
                raise ValueError("ETA list or tuple is to long")

        if isinstance(self.etd, (tuple, list)):
            if len(self.etd) == 1:
                self.etd = self.etd[0]
            elif len(self.etd) == 2:
                self.etd_min, self.etd_max = self.etd
                self.etd = None
            elif len(self.etd) == 3:
                self.etd_min, self.etd, self.etd_max = self.etd
            else:
                raise ValueError("ETD list or tuple is to long")

        if isinstance(self.eta, datetime) \
                or isinstance(self.eta_min, datetime) \
                or isinstance(self.eta_max, datetime):
            self.use_datetime = True

        if self.use_datetime:
            for attr_name in ["eta", "eta_min", "eta_max", "etd", "etd_min", "etd_max"]:
                attr = getattr(self, attr_name)
                assert attr is None \
                    or isinstance(attr, datetime), "self.%s has the wrong type (%s)" % (attr_name, type(attr))
        else:
            for attr_name in ["eta", "eta_min", "eta_max", "etd", "etd_min", "etd_max"]:
                attr = getattr(self, attr_name)
                assert attr is None \
                    or isinstance(attr, (int, float)), "self.%s has the wrong type (%s)" % (attr_name, type(attr))

    def _get_seconds(self, seconds, now):
        if self.use_datetime:
            assert isinstance(now, datetime), "When using datetime, the current time needs to be provided"
            return now + timedelta(seconds=seconds)
        return seconds

    def _get_time(self, name, now):
        value = getattr(self, name)
        if isinstance(value, datetime):
            assert isinstance(now, datetime), "When using datetime, the current time needs to be provided"
            assert self.use_datetime, "Model does not use datetime"
            return (value - now).total_seconds()
        return value

    def _set_time(self, name, seconds, now):
        seconds = self._get_seconds(seconds, now)
        setattr(self, name, seconds)

    def arrive(self, now=None):
        """
        set state to arrived
        """
        self.state = States.ARRIVED
        self.eta_max = None
        self.eta_min = None
        self.set_eta(0, now)

    def cancel(self):
        """
        set state to canceled
        """
        if self.state in [States.NEW, States.SCHEDULED, States.DEPARTED]:
            self.state = States.CANCELED
        self.canceled = True

    def depart(self, now=None):
        """
        set state to departed
        """
        self.state = States.DEPARTED
        self.etd_max = None
        self.etd_min = None
        self.set_etd(0, now)

    def finish(self, now=None):
        """
        set state to finished
        """
        self.state = States.FINISHED
        self.set_finish(0, now)

    def schedule(self, start, finish, now=None):
        """
        set state to scheduled
        """
        assert finish >= start, "Finish-time must be larger than start-time"
        self.state = States.SCHEDULED
        self.set_start(start, now)
        self.set_finish(finish, now)

    def start(self, now=None):
        """
        set state to started
        """
        self.state = States.STARTED
        self.set_start(0, now)

    def get_start(self, now=None):
        """
        get (scheduled) start time
        """
        return self._get_time("schedule_start", now)

    def get_finish(self, now=None):
        """
        get (scheduled) finish time
        """
        return self._get_time("schedule_finish", now)

    def get_eta(self, now=None):
        """
        get eta
        """
        return self._get_time("eta", now)

    def get_eta_max(self, now=None):
        """
        get max eta
        """
        return self._get_time("eta_max", now)

    def get_eta_min(self, now=None):
        """
        get min eta
        """
        return self._get_time("eta_min", now)

    def get_etd(self, now=None):
        """
        get etd
        """
        return self._get_time("etd", now)

    def get_etd_max(self, now=None):
        """
        get max etd
        """
        return self._get_time("etd_max", now)

    def get_etd_min(self, now=None):
        """
        get min etd
        """
        return self._get_time("etd_min", now)

    def set_start(self, seconds, now=None):
        """
        set (scheduled) start
        """
        return self._set_time("schedule_start", seconds, now)

    def set_finish(self, seconds, now=None):
        """
        set (scheduled) finish
        """
        return self._set_time("schedule_finish", seconds, now)

    def set_eta(self, seconds, now=None):
        """
        set eta
        """
        return self._set_time("eta", seconds, now)

    def set_eta_max(self, seconds, now=None):
        """
        set max eta
        """
        return self._set_time("eta_max", seconds, now)

    def set_eta_min(self, seconds, now=None):
        """
        set min eta
        """
        return self._set_time("eta_min", seconds, now)

    def set_etd(self, seconds, now=None):
        """
        set etd
        """
        return self._set_time("etd", seconds, now)

    def set_etd_max(self, seconds, now=None):
        """
        set max etd
        """
        return self._set_time("etd_max", seconds, now)

    def set_etd_min(self, seconds, now=None):
        """
        set min etd
        """
        return self._set_time("etd_min", seconds, now)


class SchedulerInterface(ABC):
    """
    Scheduler interface
    """

    def __init__(self, agent):
        self._agent = agent
        self._events = []

    def __call__(self, **kwargs):
        """
        """
        return Event(**kwargs)

    @property
    def events(self):
        """
        returns a list of registered events
        """
        return self._events

    @events.setter
    def events(self, value):
        self._events = value

    @abstractmethod
    def add(self, event, now=None):
        """
        add a new event to the scheduler
        """

    @abstractmethod
    def can_schedule(self, event, now=None):
        """
        Returns True if an event can be scheduled
        """

    def save(self, event, now=None):
        """
        save event to eventlist
        """
        try:
            response = self.add(event, now)
        except CanNotSchedule:
            return False

        if response is None or response is True:
            self._events.append(event)
            return True
        return False

    def cancel(self, event):
        """
        deletes a scheduled event
        """
        response = False
        for i, scheduled_event in enumerate(self.events):
            if scheduled_event == event:
                del self.events[i]
                response = True
                break
        return response
