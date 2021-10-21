#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
simulation interface
"""

import csv
import json
import logging
import random

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from functools import total_ordering
from functools import wraps
from heapq import heappop
from heapq import heappush
from time import time
from typing import Any

from iams.exceptions import StopSimulation


logger = logging.getLogger(__name__)


class Priority(Enum):
    """
    Event-states enum
    """
    HIGHEST = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    LOWEST = 9


class Agent(ABC):
    """
    basic agent class for simulations
    """
    # pylint: disable=no-member

    def __call__(self, simulation, dryrun):
        """
        init agent in simulation
        """

    def __hash__(self):
        return hash(str(self))

    @abstractmethod
    def __str__(self):
        """
        Agents name
        """

    @abstractmethod
    def asdict(self) -> dict:
        """
        returns the agent object's data as a dictionary
        """

    @abstractmethod
    def attributes(self) -> dict:
        """
        returns the agent attributes as a dictionary
        """


def manage_random_state(func):
    """
    manages the random-state to get consistend results between different simulation runs
    """
    def generator(seed, args, kwargs):
        random.seed(seed)
        state = random.getstate()
        iterator = func(*args, **kwargs)
        while True:
            random.setstate(state)
            result = next(iterator)  # pylint: disable=stop-iteration-return
            state = random.getstate()
            yield result

    @wraps(func)
    def wrapper(*args, **kwargs):
        return generator(random.random(), args, kwargs)

    return wrapper


@total_ordering
@dataclass(frozen=True)
class Queue:  # pylint: disable=too-many-instance-attributes
    """
    Storage of simulation events
    """
    time: float = field(compare=True, repr=True, hash=False)
    obj: Any = field(compare=False, repr=False, hash=False)
    callback: str = field(compare=False, repr=True, hash=False)
    dt: float = field(compare=True, repr=False, hash=False)  # pylint: disable=invalid-name
    priority: Priority = field(default=Priority.NORMAL, compare=True, repr=True, hash=True)
    args: list = field(compare=False, repr=False, default_factory=list, hash=False)
    kwargs: dict = field(compare=False, repr=False, default_factory=dict, hash=False)
    deleted: bool = field(compare=False, repr=False, hash=False, default=False)

    def __str__(self):
        return "%.4f:%s:%s" % (self.time, self.obj, self.callback)  # pylint: disable=consider-using-f-string

    def __lt__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) < (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __le__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) <= (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __eq__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) == (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __ne__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) != (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __ge__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) >= (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __gt__(self, other):
        if isinstance(other, Queue):
            return (self.time, self.priority.value, other.dt) > (other.time, other.priority.value, self.dt)
        raise NotImplementedError

    def __post_init__(self):
        if isinstance(self.priority, str):
            # pylint: disable=no-member
            try:
                priority = Priority[self.priority.upper()]
            except KeyError:
                priority = Priority.NORMAL
            object.__setattr__(self, 'priority', priority)

    def cancel(self):
        """
        cancel event from queue
        """
        object.__setattr__(self, 'deleted', True)


class SimulationInterface(ABC):  # pylint: disable=too-many-instance-attributes
    """
    simulation interface
    """

    def __init__(self, df, name, folder, fobj, seed, start, stop):  # pylint: disable=too-many-arguments
        logger.info("=== Start: %s", datetime.now())
        logger.info("=== Initialize %s", self.__class__.__qualname__)
        self._agents = {}
        self._csv_writer = None
        self._df = df
        self._events = 0
        self._fobj = fobj
        self._folder = folder
        self._limit = stop
        self._name = name
        self._queue = []
        self._time = start
        logger.info("=== Setting random-seed: %s", seed)
        random.seed(seed)
        self.post_init()

    def post_init(self):
        """
        executes after init
        """
        self._df(**self.df_kwargs())

    def df_kwargs(self):  # pylint: disable=no-self-use
        """
        returns the directors facilitator keyword arguments
        """
        return {}

    def __call__(self, dryrun, settings):
        timer = time()

        logger.info("=== Setup simulation")
        self.setup(**settings)

        logger.info("=== Init agents")
        for agent in sorted(self._agents):
            self._agents[agent](self, dryrun)

        logger.info("=== Start simulation")
        while self._queue:
            event = heappop(self._queue)

            if event.deleted:
                continue

            if self._limit is not None and event.time > self._limit:
                self._events -= 1
                break

            delta = event.time - self._time
            if delta > 0:  # pragma: no branch
                logger.debug("Update timestamp: %.3f", event.time)

            # callback to act interact with event, gather statistics, etc
            self.event_callback(event, delta, dryrun)

            # update time
            self._time = event.time

            # run event
            try:
                getattr(event.obj, event.callback)(self, *event.args, **event.kwargs)
            except StopSimulation as exception:
                logger.info("Simulation stopped: %s", exception)
                break

        # reduce processed events by events still in queue
        self._events -= len(self._queue)

        logger.info("=== Calling stop on agents")
        for agent in sorted(self._agents):
            try:
                self._agents[agent].stop(self, dryrun)
            except (AttributeError, TypeError, NotImplementedError):
                logger.debug("%s does not provide a stop method", agent)
        logger.info("=== Stop simulation")
        self.stop(dryrun)
        timer = time() - timer
        eps = self._events / timer
        if timer < 90:  # pragma: no branch
            timer = "%.3f seconds" % timer  # pylint: disable=consider-using-f-string
        elif timer < 7200:  # pragma: no cover
            timer = "%.3f minutes" % (timer / 60)  # pylint: disable=consider-using-f-string
        else:  # pragma: no cover
            timer = "%.3f hours" % (timer / 3600)  # pylint: disable=consider-using-f-string
        logger.info("=== End: %s", datetime.now())
        logger.info("=== Processed %s events in %s (%.2f per second)", self._events, timer, eps)

    def __str__(self):
        return f'{self.__class__.__qualname__}({self._name})'

    @property
    def df(self):  # pylint: disable=invalid-name
        """
        returns the directory facilitator
        """
        return self._df

    def get_state(self, **kwargs):
        """
        write system state
        """
        kwargs.update(self.asdict() or {})
        for agent, _ in self.df.agents():
            for key, value in self._agents[agent].asdict().items():
                kwargs[f'{agent}_{key}'] = value
        return kwargs

    def register(self, agent):
        """
        register agent
        """
        attrs = agent.attributes() or {}
        self._df.register_agent(str(agent), **attrs)
        self._agents[str(agent)] = agent

    def agent(self, name):
        """
        iterator over all agents
        """
        return self._agents[name]

    def unregister(self, agent):
        """
        unregister agent
        """
        try:
            del self._agents[str(agent)]
        except KeyError:
            pass

    def schedule(self, obj, dt, callback, *args, priority=Priority.NORMAL, **kwargs):  # pylint: disable=invalid-name
        """
        schedules a new event
        """
        self._events += 1
        event_time = self._time + dt
        queue = Queue(
            time=event_time,
            priority=priority,
            obj=obj,
            callback=callback,
            dt=dt,
            args=args,
            kwargs=kwargs,
        )
        logger.debug("Adding %s.%s at %s to queue (%s)", obj, callback, event_time, queue.priority.name)
        heappush(self._queue, queue)
        return queue

    def write(self, data):
        """
        writes the data to the simulations fileobject
        """
        self._fobj.write(data)

    def write_json(self, data):
        """
        dumps the data as json with a newline
        """
        json.dump(data, self._fobj)
        self._fobj.write('\n')

    def write_csv(self, data):
        """
        writes a data dictionary to CSV
        """
        try:
            self._csv_writer.writerow(data)
        except AttributeError:
            self._csv_writer = csv.DictWriter(self._fobj, fieldnames=sorted(data.keys()))
            self._csv_writer.writeheader()
            self._csv_writer.writerow(data)

    def get_time(self):
        """
        returns the current simulation timeframe
        """
        return self._time

    @abstractmethod
    def setup(self, **kwargs):
        """
        called to setup the simulation
        """

    @abstractmethod
    def stop(self, dryrun):
        """
        called when the simulation is stopped
        """

    def event_callback(self, event, dt, dryrun):  # pylint: disable=invalid-name
        """
        overwrite to process event callbacks
        """

    def asdict(self) -> dict:
        """
        returns the agent object's data as a dictionary
        """
