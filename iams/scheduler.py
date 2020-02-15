#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from uuid import uuid1

import grpc

from google.protobuf.empty_pb2 import Empty

from .exceptions import EventNotFound
from .proto.simulation_pb2 import EventScheduleRequest
from .stub import SimulationStub
from .utils.grpc import framework_channel


logger = logging.getLogger(__name__)


class Scheduler(object):
    """
    Event scheduler on agents
    """

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

    def resume(self):
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = SimulationStub(channel)
                stub.resume(Empty(), timeout=10)
        except grpc.RpcError as e:
            logger.exception("error %s in calling SimulationStub.resume: %s", e.code(), e.details())

    def schedule(self, delay, callback, **kwargs):
        """
        Schedule a new event in simulation runtime
        """
        uuid = uuid1().bytes
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = SimulationStub(channel)
                response = stub.schedule(EventScheduleRequest(uuid=uuid, delay=delay), timeout=10)
        except grpc.RpcError as e:
            logger.exception("error %s in calling SimulationStub.schedule: %s", e.code(), e.details())

        logger.debug("Register execution event '%s' at %s", callback, response.time)
        self.events[uuid] = (callback, kwargs)

        return self.time + delay

    def set_event(self, uuid, time):
        self.uuid = uuid
        self.time = time

        # continue execution in main thread
        self.parent._loop_event.set()
