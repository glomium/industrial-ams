#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from uuid import uuid1

import grpc

# from google.protobuf.empty_pb2 import Empty

from .exceptions import EventNotFound
from .proto import agent_pb2
from .proto.simulation_pb2 import EventScheduleRequest
from .stub import SimulationStub
from .utils.grpc import framework_channel


logger = logging.getLogger(__name__)


class Scheduler(object):
    """
    Event scheduler on agents
    """

    def __init__(self, parent, servicer):
        self.parent = parent
        self.servicer = servicer

        self.uuid = b''
        self.time = 0.0
        self.start = True

        self.events = {}

    def __next__(self):
        logger.debug("selecting next event: %s", self.uuid)
        if self.uuid == b'':
            if self.start:
                return "simulation_start", {}
            else:
                return "simulation_finish", {}

        try:
            callback, kwargs = self.events.pop(self.uuid)
        except KeyError:
            raise EventNotFound("%s could not be found", self.uuid.hex())
        return callback, kwargs

    def __iter__(self):
        return self

    def resume(self):
        self.servicer.queue.put(None)

    def metric(self, data):
        self.servicer.queue.put(agent_pb2.SimulationMetric(metrics=data))

    def log(self, message):
        self.servicer.queue.put(agent_pb2.SimulationLog(
            text=message,
        ))

    def schedule(self, delay, callback, **kwargs):
        """
        Schedule a new event in simulation runtime
        """
        uuid = uuid1().bytes
        if self.servicer.queue is None:
            try:
                with framework_channel(credentials=self.parent._credentials) as channel:
                    stub = SimulationStub(channel)
                    stub.schedule(EventScheduleRequest(uuid=uuid, delay=delay), timeout=10)
            except grpc.RpcError as e:
                logger.exception("error %s in calling SimulationStub.schedule: %s", e.code(), e.details())
        else:
            self.servicer.queue.put(agent_pb2.SimulationSchedule(
                uuid=uuid,
                delay=delay,
            ))

        logger.debug("Register execution event '%s' with a delay of %s", callback, delay)
        self.events[uuid] = (callback, kwargs)

        return self.time + delay

    def set_event(self, uuid, time):
        self.uuid = uuid
        self.time = time

        # continue execution in main thread
        self.parent._loop_event.set()
