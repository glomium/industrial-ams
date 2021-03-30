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
    eta: Union[list, tuple, int, float, datetime] = field(repr=True, init=True, compare=True)
    duration: Union[int, float]
    callback: str
    args: Union[list, tuple] = field(default_factory=list, repr=False, init=True, compare=True)
    kwargs: dict = field(default_factory=dict, repr=False, init=True, compare=True)

    uid: int = field(default=0, repr=False, init=False, compare=False, hash=True)
    state: States = field(default=States.NEW, repr=True, init=True, compare=False)
    schedule_start: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    schedule_finish: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta_min: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta_max: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta_lane: int = field(default=None, repr=False, init=False, compare=False)
    etd: Union[list, tuple, int, float, datetime, None] = field(default=None, repr=True, init=True, compare=True)
    etd_min: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    etd_max: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    etd_lane: int = field(default=None, repr=False, init=False, compare=False)
    use_datetime: bool = field(default=False, repr=False, init=False, compare=False)
    setup: Union[int, float] = field(default=0, repr=False, init=True, compare=True)
    setup_condition: Union[str, None] = field(default=None, repr=False, init=True, compare=True)
    canceled: bool = field(default=False, repr=False, init=False, compare=False)

    def __hash__(self):
        return self.uid

    def __post_init__(self):  # pylint: disable=too-many-branches

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

        if self.eta is None and (self.eta_min is None or self.eta_max is None):
            raise ValueError("ETA must be set")
        self.use_datetime = isinstance(self.eta, datetime) or isinstance(self.eta_min, datetime) or isinstance(self.eta_max, datetime)  # noqa: E501

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

        if self.use_datetime:
            for attr_name in ["eta", "eta_min", "eta_max", "etd", "etd_min", "etd_max"]:
                attr = getattr(self, attr_name)
                if attr is not None and not isinstance(attr, datetime):
                    raise ValueError("self.%s has the wrong type (%s)" % (attr_name, type(attr)))
        else:
            for attr_name in ["eta", "eta_min", "eta_max", "etd", "etd_min", "etd_max"]:
                attr = getattr(self, attr_name)
                if attr is not None and not isinstance(attr, (int, float)):
                    raise ValueError("self.%s has the wrong type (%s)" % (attr_name, type(attr)))

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

    def arrive(self, time):
        """
        set state to arrived
        """
        self.state = States.ARRIVED
        self.eta_max = None
        self.eta_min = None
        if self.use_datetime:
            self.set_eta(0, time)
        else:
            self.set_eta(time)

    def cancel(self):
        """
        set state to canceled
        """
        if self.state in [States.NEW, States.SCHEDULED, States.DEPARTED]:
            self.state = States.CANCELED
        self.canceled = True

    def depart(self, time):
        """
        set state to departed
        """
        self.state = States.DEPARTED
        self.etd_max = None
        self.etd_min = None
        if self.use_datetime:
            self.set_etd(0, time)
        else:
            self.set_etd(time)

    def finish(self, time):
        """
        set state to finished
        """
        self.state = States.FINISHED
        if self.use_datetime:
            self.set_finish(0, time)
        else:
            self.set_finish(time)

    def schedule(self, start, finish, now=None):
        """
        set state to scheduled
        """
        assert finish >= start, "Finish-time must be larger than start-time"
        self.state = States.SCHEDULED
        self.set_start(start, now)
        self.set_finish(finish, now)

    def start(self, time):
        """
        set state to started
        """
        self.state = States.STARTED
        if self.use_datetime:
            self.set_start(0, time)
        else:
            self.set_start(time)

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
    event_class = Event

    def __init__(self, agent):
        self._agent = agent
        self._events = []

    def __call__(self, **kwargs):
        return self.event_class(**kwargs)

    def get_events(self, new_events=None):
        """
        returns a list of registered events
        """
        delete = []
        for i, event in enumerate(self._events, 1):
            event.uid = i
            if event.state in [States.DEPARTED, States.CANCELED]:
                delete.append(event)
                continue
            yield event

        if isinstance(new_events, self.event_class):
            new_events = [new_events]
        elif new_events is None:
            new_events = []

        for i, event in enumerate(new_events, len(self._events)):
            assert event.state == States.NEW, "Event needs to be new"
            event.uid = len(self._events) + 1
            yield event

        for event in delete:
            try:
                self._events.remove(event)
            except ValueError:
                pass
            else:
                self.cleanup(event)

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

    def cleanup(self, event):
        """
        callback after event was removed
        """

    def save(self, event, now=None):
        """
        save event to eventlist
        """
        try:
            response = self.add(event, now)
        except CanNotSchedule:
            return False

        if not isinstance(response, Event):
            raise ValueError("'event' has the wrong class")

        self._events.append(response)
        return True
