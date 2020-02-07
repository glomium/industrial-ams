#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from uuid import uuid1

import grpc

from .exceptions import EventNotFound
from .rpc.simulation_pb2 import EventRegister
from .stubs import SimulationStub
from .utils import framework_channel


logger = logging.getLogger(__name__)


class Runtime(object):

    def __init__(self, parent):
        self.parent = parent

        self.uuid = None
        self.time = 0.0

        self.events = {}

    def __next__(self):
        uuid = self.uuid
        try:
            callback, kwargs = self.events.pop(uuid)
        except KeyError:
            raise EventNotFound("%s could not be found", uuid.hex())
        return callback, kwargs

    def __iter__(self):
        return self

    def resume(self):
        try:
            with framework_channel() as channel:
                stub = SimulationStub(channel)
                stub.resume(EventRegister(), timeout=10)
            return True
        except grpc.RpcError as e:
            logger.exception("error %s in simulation.resume: %s", e.code(), e.details())
            return False

    def schedule(self, delay, callback, **kwargs):
        uuid = uuid1().bytes
        try:
            with framework_channel() as channel:
                stub = SimulationStub(channel)
                response = stub.schedule(EventRegister(uuid=uuid, delay=delay), timeout=10)
        except grpc.RpcError as e:
            logger.exception("error %s in calling SimulationStub.schedule: %s", e.code(), e.details())

        logger.debug("Register execution event at %s", response.time)
        self.events[uuid] = (callback, kwargs)

    def event_trigger(self, uuid, time):
        self.uuid = uuid
        self.time = time

        # continue execution in main thread
        # TODO
        self.parent._loop_event.set()
