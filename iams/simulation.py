#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from uuid import uuid1

import grpc

from .exceptions import EventNotFound
from .proto.simulation_pb2 import EventScheduleRequest
from .stub import SimulationStub
from .utils.grpc import framework_channel

import json
import random

from heapq import heappush
from heapq import heappop
from threading import Event
# from threading import Thread
from uuid import UUID

# import simpy

# from google.protobuf.empty_pb2 import Empty

# from .rpc.agent_pb2 import SimulationData
# from .rpc.agent_pb2_grpc import AgentStub


logger = logging.getLogger(__name__)


class Runtime(object):

    # === TODO ================================================================

    def __init__(self, parent, until=None, prefix="", seed=None) -> None:
        self.event = Event()
        self.start_event = Event()
        self.parent = parent
        self.until = until or 300  # FIXME
        self.seed = seed or random.randint(100000000000, 999999999999)
        # self.runtime = simpy.Environment()
        self.prefix = "s_%s" % prefix
        super().__init__()
        self.time = 0.0
        self.heap = []
        self.daemon = True
        self.agents = []
        self.booting = set()
        self.current_agent = None

    def add_event(self, name, uuid, delay):
        time = self.time + delay
        logger.debug("Adding event at %s for agent %s (delay=%s)", time, name, delay)
        heappush(self.heap, (time, name, uuid))
        return time, (name == self.current_agent or self.current_agent is None)

    def add_agent(self, name, config):
        config["image"]["logging_name"] = name
        container = f"{self.prefix!s}{name!s}"

        # logger.debug("Adding container %s with config %s", container, config)
        # self.agents[container] = Agent(container, self.runtime, config)
        self.booting.add(container)

        # create default values for topology and rewrite agent names with prefix
        if "topology" not in config:
            config["topology"] = {}
        for agent in list(config["topology"].keys()):
            new = f"{self.prefix!s}{agent!s}"
            config["topology"][new] = config["topology"].pop(agent)

        # store config data in etcd
        for var in ["config", "service", "topology"]:
            path = f"agents/{container!s}/{var!s}"
            path = path.encode('utf-8')
            if var in config:
                data = json.dumps(config[var])
            else:
                data = "{}"
            self.parent.etcd_client.put(path, data)

        self.agents.append(container)

        self.parent.agent_upgrade(
            container,
            data=config["image"],
            update=True,
            create=True,
        )

    def booted(self, name):
        try:
            self.booting.remove(name)
        except KeyError:
            logger.warning('Could not remove %s from booting - stopping simulation', name)
            for container in self.agents:
                self.parent.agent_destroy(container)
        if not self.booting:
            self.start_event.set()

    def run(self):
        logger.info("start simulation")
        self.event.set()

        while True:
            if self.booting:
                self.start_event.clear()
                logger.debug("waiting for containers to bootup")
                self.start_event.wait()

            if not self.event.wait(30):
                logger.info("waited 30s on the respone of agent %s", self.current_agent)
            if not self.event.wait(30):
                logger.warning("waited 60s on the respone of agent %s - closing simulation", self.current_agent)
                break
            self.event.clear()

            # execute step on agent
            try:
                self.time, self.current_agent, uuid = heappop(self.heap)
            except IndexError:
                logger.info("Simulation finished - no more events in queue")
                break

            if self.until is not None and self.time > self.until:
                logger.info("Simulation finished - time limit reached")
                break

            with framework_channel(self.current_agent):
                logger.info(
                    "continue execution of simulation on %s at %s (%s)",
                    self.current_agent,
                    self.time,
                    UUID(bytes=uuid),
                )
                # stub = AgentStub(channel)
                # stub.simulation_continue(SimulationData(uuid=uuid, time=self.time), timeout=10)

        logger.debug("Stopping all containers")
        for container in self.agents:
            self.parent.agent_destroy(container)

    # === END TODO ============================================================


class Scheduler(object):

    def __init__(self, parent):
        self.parent = parent

        self.uuid = None
        self.time = 0.0

        self.events = {}

    def __next__(self):
        try:
            callback, kwargs = self.events.pop(self.uuid)
        except KeyError:
            raise EventNotFound("%s could not be found", self.uuid.hex())
        return callback, kwargs

    def __iter__(self):
        return self

    def schedule(self, delay, callback, **kwargs):
        """
        Schedule a new event in simulation runtime
        """
        uuid = uuid1().bytes
        try:
            with framework_channel() as channel:
                stub = SimulationStub(channel)
                response = stub.schedule(EventScheduleRequest(uuid=uuid, delay=delay), timeout=10)
        except grpc.RpcError as e:
            logger.exception("error %s in calling SimulationStub.schedule: %s", e.code(), e.details())

        logger.debug("Register execution event at %s", response.time)
        self.events[uuid] = (callback, kwargs)

    def set_event(self, uuid, time):
        self.uuid = uuid
        self.time = time

        # continue execution in main thread
        self.parent._loop_event.set()
