#!/usr/bin/python
# ex:set fileencoding=utf-8:

import json
import logging
import random

# from logging.config import dictConfig
# from dataclasses import asdict
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from heapq import heappop
from heapq import heappush
from time import time
from typing import Any


logger = logging.getLogger(__name__)


@dataclass(order=True)
class Queue:
    time: float
    name: str
    obj: Any = field(compare=False, repr=False)
    callback: str = field(compare=False)
    dt: float = field(compare=False, repr=False)
    args: list = field(compare=False, repr=False, default_factory=list)
    kwargs: dict = field(compare=False, repr=False, default_factory=dict)

    def __str__(self):
        return "%.4f:%s:%s" % (self.time, self.name, self.callback)


class SimulationInterface(ABC):

    def __init__(self, df, name, folder, fobj, seed, start, stop):
        logger.info("=== Initialize %r", self.__class__)
        self._agents = []
        self._df = df
        self._fobj = fobj
        self._folder = folder
        self._limit = stop
        self._name = name
        self._queue = []
        self._time = float(start)
        logger.info("=== Setting random-seed: %s", seed)
        random.seed(seed)

    def __call__(self, dryrun, settings):
        timer = time()
        events = 0

        logger.info("=== Setup simulation")
        self.setup(**settings)

        logger.info("=== Init agents")
        for agent in self._agents:
            agent(self, dryrun)

        if self._queue:
            logger.info("=== Start simulation")
        else:
            logger.error("(!) Event queue is emtpy - use %s.setup to initialize events" % self.__class__.__qualname__)

        while self._queue:
            event = heappop(self._queue)

            if self._limit is not None and event.time > self._limit:
                break

            dt = event.time - self._time
            if dt > 0:  # pragma: no branch
                logger.debug("Update timestamp: %.3f", event.time)

            # callback to act interact with event, gather statistics, etc
            self.event_callback(event, dt, dryrun)

            # update time
            self._time = event.time

            # run event-callback metod
            getattr(event.obj, event.callback)(self, *event.args, **event.kwargs)
            events += 1

        logger.info("=== Stop simulation")
        self.stop(dryrun)
        timer = time() - timer
        eps = events / timer
        if timer < 90:  # pragma: no branch
            timer = "%.3f seconds" % timer
        elif timer < 7200:  # pragma: no cover
            timer = "%.3f minutes" % (timer / 60)
        else:  # pragma: no cover
            timer = "%.3f hours" % (timer / 3600)
        logger.info("=== Processed %s events in %s (%.2f per second)", events, timer, eps)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__qualname__, self._name)

    def register(self, agent):
        self._agents.append(agent)

    # def unregister(self, name):
    #     del self._agents[name]

    def schedule(self, obj, dt, callback, *args, **kwargs):
        time = self._time + dt
        logger.debug("Adding %s.%s at %s to queue", obj, callback, time)
        heappush(self._queue, Queue(time, str(obj), obj, callback, dt, args, kwargs))

    def write(self, data):
        self._fobj.write(data)

    def write_json(self, data):
        json.dump(data, self._fobj)
        self._fobj.write('\n')

    def get_time(self):
        return self._time

    @abstractmethod
    def setup(self, **kwargs):  # pragma: no cover
        pass

    @abstractmethod
    def stop(self, dryrun):  # pragma: no cover
        pass

    def event_callback(self, event, dt, dryrun):
        pass
