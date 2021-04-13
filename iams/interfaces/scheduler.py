#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams scheduler interface
"""

import logging

from abc import ABC
from abc import abstractmethod
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from enum import Enum
from enum import auto
from functools import total_ordering
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
@total_ordering
class ETX:  # pylint: disable=too-many-instance-attributes
    """
    Manges ETA and ETD times
    """
    time: Union[int, float, datetime] = field(default=None, init=True, compare=True)
    # hard constraints (these values are not allowed to change)
    constraint_high: Union[int, float, datetime] = field(default=None, init=True, compare=False)
    constraint_low: Union[int, float, datetime] = field(default=None, init=True, compare=False)
    # soft constraints (these values are subject to change)
    time_high: Union[int, float, datetime] = field(default=None, init=True, compare=False)
    time_low: Union[int, float, datetime] = field(default=None, init=True, compare=False)
    # minimum space (in seconds) between time_high and time or time_low and time
    margin_low: Union[int, float] = field(default=0, init=True, compare=False)
    margin_high: Union[int, float] = field(default=0, init=True, compare=False)
    use_datetime: bool = field(default=False, init=True, compare=False)

    def __post_init__(self):  # pylint: disable=too-many-branches
        attrs = ["time", "constraint_high", "constraint_low", "time_high", "time_low"]

        # set use_datetime
        for attr in attrs:
            if isinstance(getattr(self, attr), datetime):
                self.use_datetime = True
                break

        # validate inputs
        if self.use_datetime:
            for attr in attrs:
                if getattr(self, attr) is not None and not isinstance(getattr(self, attr), datetime):
                    raise ValueError(f"{attr} is not datetime")
        else:
            for attr in attrs:
                if getattr(self, attr) is not None and not isinstance(getattr(self, attr), (int, float)):
                    raise ValueError(f"{attr} is not a number")

        # validate margins
        if self.margin_low < 0 or self.margin_high < 0:
            raise ValueError('Margins need to be positive')

        # set default values (constraints)
        if self.constraint_high is not None and self.time_high is None:
            self.time_high = self.constraint_high
        if self.constraint_low is not None and self.time_low is None:
            self.time_low = self.constraint_low

        # set default values (time high)
        if self.time_high is None and self.time is not None:
            if self.use_datetime:
                self.time_high = self.time + timedelta(seconds=self.margin_high)
            else:
                self.time_high = self.time + self.margin_high

        # set default values (time low)
        if self.time_low is None and self.time is not None:
            if self.use_datetime:
                self.time_low = self.time - timedelta(seconds=self.margin_low)
            else:
                self.time_low = self.time - self.margin_low

        self.validate()

    def __bool__(self):
        return self.constraint_high is not None and self.constraint_low is not None

    def __sub__(self, other):
        if not self.use_datetime and self.time and isinstance(other, (int, float)):
            return self.time - other
        raise NotImplementedError

    def __eq__(self, other):
        if other is None:
            return False
        if isinstance(other, ETX):
            return self.time == other.time
        if isinstance(other, (datetime, int, float)):
            return self.time == other
        raise NotImplementedError(f"{self.__class__.__qualname__}.__eq__ is not implemented for {type(other)}")

    def __lt__(self, other):
        if isinstance(other, ETX):
            value1 = self.constraint_low if self.time is None else self.time
            value2 = other.constraint_low if other.time is None else other.time
            return value1 < value2
        if isinstance(other, (datetime, int, float)):
            value = self.time if self.constraint_low is None else self.constraint_low
            return value < other
        raise NotImplementedError(f"{self.__class__.__qualname__}.__lt__ is not implemented for {type(other)}")

    def __str__(self):
        if self.time is None:
            return f'{self.__class__.__qualname__}()'
        return f'{self.__class__.__qualname__}({self.time})'

    def validate(self):  # pylint: disable=too-many-branches
        """
        raises ValueError if not valid
        """
        if self.constraint_high is not None and self.constraint_low is not None and \
                self.constraint_high < self.constraint_low:
            raise ValueError("contraint_high is smaller than constraint_low")

        if self.time_high is not None and self.time_low is not None and \
                self.time_high < self.time_low:
            raise ValueError("time_high is smaller than time_low")

        if self.constraint_high is not None and self.constraint_low is not None:
            if self.use_datetime:
                if (self.constraint_high - self.constraint_low).total_seconds() < self.margin_high + self.margin_low:
                    raise ValueError("contraint_high and constraint_low need to be within the margins")
            else:
                if self.constraint_high - self.constraint_low < self.margin_high + self.margin_low:
                    raise ValueError("contraint_high and constraint_low need to be within the margins")

        if self.time_high is not None and self.time is not None:
            if self.use_datetime:
                if (self.time_high - self.time).total_seconds() < self.margin_high:
                    self.time_high = self.time + timedelta(seconds=self.margin_high)
            else:
                if self.time_high - self.time < self.margin_high:
                    self.time_high = self.time + self.margin_high

        if self.time_low is not None and self.time is not None:
            if self.use_datetime:
                if (self.time - self.time_low).total_seconds() < self.margin_low:
                    self.time_low = self.time - timedelta(seconds=self.margin_low)
            else:
                if self.time - self.time_low < self.margin_low:
                    self.time_low = self.time - self.margin_low

    def get(self, now=None):
        """
        get time
        """
        if self.use_datetime and self.time is not None and now is not None:
            return (self.time - now).total_seconds()
        return self.time

    def set(self, time, now=None):
        """
        set time
        """
        if self.use_datetime and now is not None and not isinstance(time, datetime):
            self.time = now + timedelta(seconds=time)
        else:
            self.time = time

    def get_constraints(self, now=None):
        """
        get constraint
        """
        if self.use_datetime and now is not None:
            if self.constraint_low is None:
                low = None
            else:
                low = (self.constraint_low - now).total_seconds()

            if self.constraint_high is None:
                high = None
            else:
                high = (self.constraint_high - now).total_seconds()
            return low, high

        return self.constraint_low, self.constraint_high

    def get_range(self, now):
        """
        get constraint
        """

    def set_constraints(self, lower, upper, now=None):
        """
        set constraint
        """
        if lower is not None and upper is not None:
            if self.use_datetime:
                diff = (upper - lower).total_seconds()
            else:
                diff = upper - lower
            if diff < self.margin_high + self.margin_low:
                raise ValueError("Upper-bond ({%s}) or lower-bond ({lower}) are out of their margins")

        if self.use_datetime and now is not None:
            if lower is not None:
                lower = now + timedelta(seconds=lower)
            if upper is not None:
                upper = now + timedelta(seconds=upper)
        self.constraint_low, self.constraint_high = lower, upper

    def set_range(self, low, high):
        """
        set range
        """


@dataclass
@total_ordering
class Event:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """
    Schedule events
    """
    duration: Union[int, float]
    callback: str
    args: Union[list, tuple] = field(default_factory=list, repr=False, init=True, compare=True)
    kwargs: dict = field(default_factory=dict, repr=False, init=True, compare=True)

    uid: int = field(default=0, repr=False, init=False, compare=False, hash=True)
    state: States = field(default=States.NEW, repr=True, init=True, compare=False)
    eta: Union[dict, list, tuple, ETX] = field(default=None, repr=True, init=True, compare=True)
    etd: Union[dict, list, tuple, ETX] = field(default=None, repr=True, init=True, compare=True)

    schedule_start: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    schedule_finish: Union[int, float, datetime] = field(default=None, repr=True, init=False, compare=False)
    eta_lane: int = field(default=None, repr=False, init=False, compare=False)
    etd_lane: int = field(default=None, repr=False, init=False, compare=False)
    use_datetime: bool = field(default=False, repr=False, init=False, compare=False)
    setup: Union[int, float] = field(default=0, repr=False, init=True, compare=True)
    setup_condition: Union[str, None] = field(default=None, repr=False, init=True, compare=True)
    canceled: bool = field(default=False, repr=False, init=False, compare=False)

    __eta_states__ = {States.NEW, States.SCHEDULED, States.ARRIVED}

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        if isinstance(other, Event):
            return self.uid == other.uid
        raise NotImplementedError

    def __lt__(self, other):
        if isinstance(other, Event):
            if self.state in self.__eta_states__ and other.state in self.__eta_states__:
                return (self.eta, self.duration, self.uid) < (other.eta, other.duration, other.uid)
            if self.state.value == other.state.value:
                if self.state == States.STARTED:
                    return (self.schedule_start, self.duration, self.uid) < (other.schedule_start, other.duration, other.uid)  # noqa: E501
                if self.state == States.FINISHED:
                    return (self.schedule_finish, self.duration, self.uid) < (other.schedule_finish, other.duration, other.uid)  # noqa: E501
                return self.eta < other.eta
            return other.state.value < self.state.value
        raise NotImplementedError

    def __post_init__(self):  # pylint: disable=too-many-branches

        if isinstance(self.eta, dict):
            self.eta = ETX(**self.eta)
        elif isinstance(self.eta, (tuple, list)):
            if len(self.eta) == 1:
                self.eta = ETX(constraint_low=self.eta[0], constraint_high=self.eta[0])
            elif len(self.eta) == 2:
                self.eta = ETX(constraint_low=self.eta[0], constraint_high=self.eta[1])
            elif len(self.eta) == 3:
                self.eta = ETX(constraint_low=self.eta[0], time=self.eta[1], constraint_high=self.eta[2])
            else:
                raise ValueError("ETA list or tuple is to long")
        elif isinstance(self.eta, (int, float, datetime)):
            self.eta = ETX(constraint_low=self.eta, constraint_high=self.eta, time=self.eta)
        elif self.eta is None:
            self.eta = ETX()
        if not isinstance(self.eta, ETX):
            raise ValueError(f"ETA needs to be an instance of {ETX.__qualname__} and not {type(self.eta)}")

        if isinstance(self.etd, dict):
            self.etd = ETX(**self.etd)
        elif isinstance(self.etd, (tuple, list)):
            if len(self.etd) == 1:
                self.etd = ETX(constraint_low=self.etd[0], constraint_high=self.etd[0])
            elif len(self.etd) == 2:
                self.etd = ETX(constraint_low=self.etd[0], constraint_high=self.etd[1])
            elif len(self.etd) == 3:
                self.etd = ETX(constraint_low=self.etd[0], time=self.etd[1], constraint_high=self.etd[2])
            else:
                raise ValueError("ETD list or tuple is to long")
        elif isinstance(self.etd, (int, float, datetime)):
            self.etd = ETX(constraint_low=self.etd, constraint_high=self.etd, time=self.etd)
        elif self.etd is None:
            self.etd = ETX()
        if not isinstance(self.etd, ETX):
            raise ValueError(f"ETD needs to be an instance of {ETX.__qualname__} and not {type(self.etd)}")

        # sync use_datetime
        self.use_datetime = self.eta.use_datetime or self.etd.use_datetime
        self.eta.use_datetime = self.use_datetime
        self.etd.use_datetime = self.use_datetime

        if not bool(self.eta):
            raise ValueError("ETA needs to be set")
        # if not bool(self.eta) and not bool(etd):
        #     raise ValueError("ETA or ETD need to be set")

        if bool(self.eta) and bool(self.etd):
            self.state = States.SCHEDULED

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

    def eta_constraints(self, now=None):
        """
        get constraints from ETA
        """
        return self.eta.get_constraints(now)

    def etd_constraints(self, now=None):
        """
        get constraints from ETD
        """
        return self.etd.get_constraints(now)

    def arrive(self, time):
        """
        set state to arrived
        """

        self.state = States.ARRIVED
        self.eta.set(time)

    def cancel(self):
        """
        set state to canceled
        """
        if self.state in {States.NEW, States.SCHEDULED, States.DEPARTED}:
            self.state = States.CANCELED
        self.canceled = True

    def depart(self, time):
        """
        set state to departed
        """
        self.state = States.DEPARTED
        self.etd.set(time)

    def finish(self, time):
        """
        set state to finished
        """
        self.state = States.FINISHED
        if self.use_datetime:
            self.set_finish(0, time)
        else:
            self.set_finish(time)

    def schedule_eta(self, lower, upper=None, now=None):
        """
        schedule eta
        """
        if upper is None:
            if self.eta.use_datetime:
                upper = lower + timedelta(seconds=self.eta.margin_high + self.eta.margin_low)
            else:
                upper = lower + self.eta.margin_high + self.eta.margin_low
        self.eta.set_constraints(lower, upper, now)
        if bool(self.eta) and bool(self.etd):
            self.state = States.SCHEDULED

    def schedule_etd(self, lower, upper=None, now=None):
        """
        schedule etd
        """
        if upper is None:
            if self.etd.use_datetime:
                upper = lower + timedelta(seconds=self.etd.margin_high + self.etd.margin_low)
            else:
                upper = lower + self.etd.margin_high + self.etd.margin_low
        self.etd.set_constraints(lower, upper, now)
        if bool(self.eta) and bool(self.etd):
            self.state = States.SCHEDULED

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


class SchedulerInterface(ABC):
    """
    Scheduler interface
    """
    event_class = Event

    def __init__(self, agent):
        self._agent = agent
        self._events = []
        self._counter = 1

    def __call__(self, **kwargs):
        event = self.event_class(**kwargs)
        event.uid = self._counter
        self._counter += 1
        return event

    def __len__(self):
        return len(self._events)

    @abstractmethod
    def add(self, event, now=None):
        """
        add a new event to the scheduler
        """

    @abstractmethod
    def validate(self, now=None) -> bool:
        """
        Returns True if the scheduler's state is valid
        """

    @abstractmethod
    def can_schedule(self, event, now=None):
        """
        Returns True if an event can be scheduled
        """

    def asdicts(self):
        """
        returns the scheduler's state as a list of dictionaries
        """
        for event in self.get_events():
            yield asdict(event)

    def cleanup(self, event):
        """
        callback after event was removed
        """

    def get_events(self, new_events=None):
        """
        returns a list of registered events
        """
        delete = []
        for event in self._events:
            if event.state in [States.DEPARTED, States.CANCELED]:
                delete.append(event)
                continue
            yield event

        if isinstance(new_events, self.event_class):
            new_events = [new_events]
        elif new_events is None:
            new_events = []

        for event in new_events:
            yield event

        for event in delete:
            try:
                self._events.remove(event)
            except ValueError:
                pass
            else:
                self.cleanup(event)

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

        logger.debug("Adding event %s to queue", response.uid)
        self._events.append(response)
        return True
