#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Union

from iams.exceptions import CanNotSchedule


logger = logging.getLogger(__name__)


@dataclass
class Event:
    eta: Union[float, datetime]
    etd: Union[float, datetime]
    duration: float

    instance: object
    callback: str
    start: float = None
    finish: float = None

    def get_etd(self, now=None):
        if isinstance(self.etd, datetime):  # pragma: no cover
            raise NotImplementedError
        else:
            return self.etd

    def get_eta(self, now=None):
        if isinstance(self.eta, datetime):  # pragma: no cover
            raise NotImplementedError
        else:
            return self.eta

    def get_duration(self):
        return self.duration


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
