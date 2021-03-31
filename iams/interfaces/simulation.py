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
from heapq import heappop
from heapq import heappush
from time import time
from typing import Any

from iams.exceptions import StopSimulation


logger = logging.getLogger(__name__)


class Agent:  # pylint: disable=no-member
    """
    basic agent class for simulations
    """

    def __call__(self, simulation, dryrun):
        """
        init agent in simulation
        """

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def asdict(self):
        """
        returns the agent object's data as a dictionary
        """
        return {
            'name': self.name,
        }


@dataclass(order=True, frozen=True)
class AgentContainer:
    """
    Storage of agent instances in simulation
    """
    name: str = field(compare=True, repr=True, hash=True)
    obj: Any = field(compare=False, repr=False, hash=False)


@dataclass(order=True, frozen=True)
class Queue:  # pylint: disable=too-many-instance-attributes
    """
    Storage of simulation events
    """
    time: float = field(compare=True, repr=True, hash=False)
    number: int = field(compare=True, repr=False, hash=True)
    obj: Any = field(compare=False, repr=False, hash=False)
    callback: str = field(compare=False, repr=True, hash=False)
    dt: float = field(compare=False, repr=False, hash=False)  # pylint: disable=invalid-name
    args: list = field(compare=False, repr=False, default_factory=list, hash=False)
    kwargs: dict = field(compare=False, repr=False, default_factory=dict, hash=False)
    deleted: bool = field(compare=False, repr=False, hash=False, default=False)

    def __str__(self):
        return "%.4f:%s:%s" % (self.time, self.obj, self.callback)

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
        self._agents = set()
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

    def __call__(self, dryrun, settings):
        timer = time()

        logger.info("=== Setup simulation")
        self.setup(**settings)

        logger.info("=== Init agents")
        for agent in sorted(self._agents):
            agent.obj(self, dryrun)

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

            try:
                # run event-callback metod
                getattr(event.obj, event.callback)(self, *event.args, **event.kwargs)
            except StopSimulation as exception:
                logger.info("Simulation stopped: %s", exception)
                break

        # reduce processed events by events still in queue
        self._events -= len(self._queue)

        logger.info("=== Calling stop on agents")
        for agent in sorted(self._agents):
            try:
                agent.obj.stop(self, dryrun)
            except (AttributeError, TypeError, NotImplementedError):
                logger.debug("%s does not provide a stop method", agent.name)
        logger.info("=== Stop simulation")
        self.stop(dryrun)
        timer = time() - timer
        eps = self._events / timer
        if timer < 90:  # pragma: no branch
            timer = "%.3f seconds" % timer
        elif timer < 7200:  # pragma: no cover
            timer = "%.3f minutes" % (timer / 60)
        else:  # pragma: no cover
            timer = "%.3f hours" % (timer / 3600)
        logger.info("=== End: %s", datetime.now())
        logger.info("=== Processed %s events in %s (%.2f per second)", self._events, timer, eps)

    def __str__(self):
        return f'{self.__class__.__qualname__}({self._name})'

    def register(self, agent):
        """
        register agent
        """
        obj = AgentContainer(str(agent), agent)
        if obj in self._agents:
            raise KeyError(f'{agent} already registered')
        self._agents.add(obj)

    def agents(self):
        """
        iterator over all agents
        """
        for agent in self._agents:
            yield agent.obj

    def unregister(self, agent):
        """
        unregister agent
        """
        obj = AgentContainer(str(agent), agent)
        self._agents.remove(obj)

    def schedule(self, obj, dt, callback, *args, **kwargs):  # pylint: disable=invalid-name
        """
        schedules a new event
        """
        self._events += 1
        event_time = self._time + dt
        logger.debug("Adding %s.%s at %s to queue", obj, callback, event_time)
        queue = Queue(
            time=event_time,
            number=self._events,
            obj=obj,
            callback=callback,
            dt=dt,
            args=args,
            kwargs=kwargs,
        )
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
