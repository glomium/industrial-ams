#!/usr/bin/python
# ex:set fileencoding=utf-8:

import logging
import random

from itertools import product
from math import sqrt

from iams.interfaces.simulation import Agent
from iams.interfaces.simulation import SimulationInterface
from iams.interfaces.simulation import manage_random_state


logger = logging.getLogger(__name__)


class Simulation(SimulationInterface):

    def setup(self, max_units, load, **kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.max_units = max_units
        self.produced = 0

        logger.info("Producing %s units", max_units)

        # storing agent by type on simulation-class
        self.sources = list(self.agent(item[0]) for item in self.df.agents(cls="MS"))
        logger.debug("Sources: %s", self.sources)
        self.destinations = list(self.agent(item[0]) for item in self.df.agents(cls="MD"))
        logger.debug("Destinations: %s", self.destinations)
        self.vehicles = list(self.agent(item[0]) for item in self.df.agents(cls="Vehicle"))
        logger.debug("Vehicles: %s", self.vehicles)

        # set destination and vehicles on source agents
        for source, destination in product(self.sources, self.destinations):
            if source.x == destination.x:
                logger.info("%s sends to %s", source, destination)
                source.destination = destination
                source.vehicles = self.vehicles
                destination.source = source

    def can_produce(self):
        """
        stop simulation after max_units have been produced
        """
        return self.max_units > self.produced

    def asdict(self):
        """
        write system state
        """
        return {
            "produced": self.produced,
            "time": self.get_time(),
        }

    def write_state(self):
        self.write_csv(self.get_state())

    def stop(self, dryrun):
        """
        called when simulation stopped
        """
        self.write_state()

    def event_callback(self, event, dt, dryrun):
        """
        triggers after every event, when the time of the next event has changed
        """
        if not dryrun and dt > 0:
            self.write_state()

        logger.debug("%s:%s@%s - %s", event.obj, event.callback, event.time, event.obj.asdict())


def distance(source, destination, speed=1):
    return round(sqrt((source.x - destination.x)**2 + (source.y - destination.y)**2) / speed)


class Vehicle(Agent):
    def __init__(self, speed, x, y, **kwargs):
        self.name = "%s" % x
        self.name = "V%s" % self.name[0]
        self.count = 0
        self.distance = 0
        self.events = []
        self.speed = speed
        self.x = x
        self.x0 = x
        self.y = y
        self.y0 = y

    def __str__(self):
        return self.name

    def attributes(self):
        return {
            'cls': str(self.__class__.__qualname__),
        }

    def asdict(self):
        return {
            'name': self.name,
            'count': self.count,
            'jobs': len(self.events),
            'distance': self.distance,
        }

    def costs(self, source, destination, priority):
        """
        calculate costs (vehicles can only drive vertical and horizontal)
        """
        if self.busy():
            return None
        return distance(source, self)

    def busy(self):
        return bool(len(self.events))

    def finish(self, simulation):
        self.events.pop(0)  # remove scheduled event from events
        self.count += 1
        self.fcfs(simulation)

    def schedule(self, simulation, source, destination, priority):
        """
        create callbacks in simulation runtime
        """
        self.distance += distance(source, self)
        self.distance += distance(source, destination)

        # time from current position to source
        schedule = distance(source, self, self.speed)
        # simulation.schedule(self, schedule, "source_reached", source)

        # load time
        schedule += source.load
        simulation.schedule(self, schedule, "resource_loaded", source)

        # time from source to destination
        schedule += distance(source, destination, self.speed)
        # simulation.schedule(self, schedule, "destination_reached", destination)

        # unload time
        schedule += destination.load
        simulation.schedule(self, schedule, "resource_unloaded", destination)

        # update position and events. inform destination about schedule
        self.events.append(schedule)
        self.x = destination.x
        self.y = destination.y
        source.scheduled.append(True)
        destination.schedule()

    def source_reached(self, simulation, source):
        """
        callback when the source is reached (not used)
        """

    def resource_loaded(self, simulation, source):
        """
        callback when resource was loaded
        """
        source.remove(simulation)

    def destination_reached(self, simulation, destination):
        """
        callback when the destination is reached (not used)
        """

    def resource_unloaded(self, simulation, destination):
        """
        callback when resource was unloaded
        """
        destination.add(simulation)
        self.finish(simulation)

    def get_agents(self, simulation):
        for agent in simulation.sources:
            if not agent.can_schedule():
                continue
            yield agent

    def fcfs(self, simulation):
        """
        First Come First Served selection of sources (FCFS)
        """
        priority = float("inf")
        selected = None
        for agent in self.get_agents(simulation):
            p = agent.priority()
            if p < priority:
                selected = agent
                priority = p

        if selected is None:
            return False

        self.schedule(simulation, selected, selected.destination, len(selected.buffered))
        return True


class MX(Agent):
    def __init__(self, x, y, time, std, size, load):
        self.name = f"{self.__class__.__qualname__}{x}"
        self.name = self.name[:-1]
        self.generator = self.iterator(random.random(), time, sqrt(std))

        self.load = load
        self.size = size
        self.x = x
        self.y = y

    def __str__(self):
        return self.name

    def attributes(self):
        return {
            'cls': str(self.__class__.__qualname__),
        }

    @manage_random_state
    def iterator(self, seed, mu, sigma):  # pylint: disable=invalid-name
        while True:
            time = round(random.gauss(mu, sigma))
            if time < 0:
                time = 0
            yield time


class MS(MX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.buffered = []
        self.destination = None
        self.generated = 0
        self.missed = 0
        self.scheduled = []
        self.vehicles = []

    def __call__(self, simulation, dryrun):
        """
        Start with generation on init
        """
        self.generate(simulation)

    def can_schedule(self):
        """
        returns if a transport can be scheduled
        """
        return len(self.buffered) > len(self.scheduled) and self.destination.can_schedule()

    def schedule(self):
        """
        schedule transport of a material
        """
        pass

    def priority(self):
        """
        return the priority of working on the agent's queue
        """
        return self.buffered[len(self.scheduled)]

    def remove(self, simulation):
        """
        remove material from source
        """
        self.buffered.pop(0)
        self.scheduled.pop(0)

    def generate(self, simulation):
        """
        generate new parts
        """
        if not simulation.can_produce():
            return None

        if self.size > len(self.buffered):
            logger.info("Product generated on %s", self.name)
            self.generated += 1
            self.buffered.append(simulation.get_time())
            simulation.produced += 1
            created = True
        else:
            logger.info("Production skipped on %s", self.name)
            self.missed += 1
            created = False

        simulation.schedule(self, next(self.generator), "generate")

        if not created:
            return None

        self.schedule_transport(simulation)

    def schedule_transport(self, simulation):
        # can not schedule as destination if full
        if not self.can_schedule():
            return False

        self.schedule_nvf(simulation)

    def schedule_nvf(self, simulation):
        """
        select nearest idle vehicle first and schedule transport on it
        """
        selected = None
        costs = float("inf")
        for vehicle in simulation.vehicles:

            response = vehicle.costs(self, self.destination, len(self.buffered))
            if response is not None and response < costs:
                costs = response
                selected = vehicle

        if selected is None:
            return False

        selected.schedule(simulation, self, self.destination, len(self.buffered))
        return True

    def asdict(self):
        return {
            'buffer': len(self.buffered),
            'generated': self.generated,
            'missed': self.missed,
            'name': self.name,
            'scheduled': len(self.scheduled),
        }


class MD(MX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.buffered = 0
        self.consumed = 0
        self.missed = 0
        self.scheduled = 0
        self.source = None
        self.started = False

    def can_schedule(self):
        """
        returns if a transport can be scheduled
        """
        return (self.buffered + self.scheduled) < self.size

    def schedule(self):
        """
        schedule transport of a material
        """
        self.scheduled += 1

    def add(self, simulation):
        """
        add material to buffer
        """
        # update settings
        self.scheduled -= 1
        self.buffered += 1

        # assert self.buffered <= self.size, "Buffer overflow: %s to large on %s" % (self.buffered, self)

        # start the consumption of resources on the destination
        # this avoids the loss of resources at the start of the simulation
        self.start(simulation)

    def consume(self, simulation):
        """
        consume material
        """
        # do not increase statistics if simulation stopped
        if not simulation.can_produce() and not self.buffered and not self.scheduled:
            return None

        if self.buffered:
            logger.info("Product consumed on %s", self.name)
            self.consumed += 1
            self.buffered -= 1
        else:
            logger.info("Production missed on %s", self.name)
            self.missed += 1

        self.schedule_consumption(simulation)

    def start(self, simulation):
        """
        start consumption of materials
        """
        if self.started is False:
            self.schedule_consumption(simulation)

    def schedule_consumption(self, simulation):
        """
        schedule next consumption event
        """
        self.started = True
        simulation.schedule(self, next(self.generator), "consume")

    def asdict(self):
        return {
            'name': self.name,
            'buffer': self.buffered,
            'missed': self.missed,
            'scheduled': self.scheduled,
            'consumed': self.consumed,
        }
